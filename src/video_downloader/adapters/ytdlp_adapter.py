from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from video_downloader.core.errors import (
    DownloadError,
    DownloadInterruptedError,
    DownloadTimeoutError,
    FormatUnavailableError,
    NetworkError,
    PrivateContentError,
    UnsupportedPlatformError,
    VideoUnavailableError,
)
from video_downloader.core.models import (
    AudioFormat,
    DownloadRequest,
    DownloadResult,
    MediaFormat,
    MediaInfo,
    ProgressCallback,
    ProgressEvent,
    ProgressStatus,
    Quality,
)
from video_downloader.core.ports import CancellationToken
from video_downloader.media.filenames import FilenamePlanner


class YoutubeDLLike(Protocol):
    def __enter__(self) -> "YoutubeDLLike": ...
    def __exit__(self, *exc_info: Any) -> None: ...
    def extract_info(self, url: str, download: bool) -> dict: ...


YoutubeDLFactory = Callable[[dict], YoutubeDLLike]

_QUALITY_FORMAT_SELECTORS = {
    Quality.BEST: "bv*+ba/b",
    Quality.P1080: "bv*[height<=1080]+ba/b[height<=1080]/b[height<=1080]",
    Quality.P720: "bv*[height<=720]+ba/b[height<=720]/b[height<=720]",
    Quality.P480: "bv*[height<=480]+ba/b[height<=480]/b[height<=480]",
}
_AUDIO_ONLY_SELECTOR = "bestaudio/best"
_PROBE_TIMEOUT_SECONDS = 30.0

_PROGRESS_STATUS_MAP = {
    "downloading": ProgressStatus.DOWNLOADING,
    "finished": ProgressStatus.POSTPROCESSING,
    "error": ProgressStatus.ERROR,
}


class _CancelledSignal(Exception):
    pass


class _SilentLogger:
    """Swallows yt-dlp's own console logging so only our translated
    DownloadError messages reach the user — yt-dlp otherwise prints its raw
    "ERROR: ..." diagnostics itself even with quiet=True, duplicating and
    contradicting our own friendly message. Only attached when not verbose,
    so --debug still surfaces yt-dlp's raw output for troubleshooting.
    """

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


class YtDlpAdapter:
    """The only module allowed to import yt_dlp directly.

    Every yt-dlp exception and raw progress dict is translated at this
    boundary so nothing above it (service, CLI, future GUI/web) ever needs
    to know yt-dlp's vocabulary or exception types.
    """

    def __init__(
        self,
        filename_planner: FilenamePlanner | None = None,
        youtube_dl_factory: YoutubeDLFactory = yt_dlp.YoutubeDL,
        cookies_from_browser: Optional[str] = None,
        cookies_file: Optional[Path] = None,
        verbose: bool = False,
    ) -> None:
        self._filename_planner = filename_planner or FilenamePlanner()
        self._youtube_dl_factory = youtube_dl_factory
        self._cookies_from_browser = cookies_from_browser
        self._cookies_file = cookies_file
        self._verbose = verbose

    def _base_opts(self) -> dict:
        opts: dict = {"quiet": True, "no_warnings": True}
        if not self._verbose:
            opts["logger"] = _SilentLogger()
        if self._cookies_from_browser:
            opts["cookiesfrombrowser"] = (self._cookies_from_browser,)
        if self._cookies_file:
            opts["cookiefile"] = str(self._cookies_file)
        return opts

    def probe(self, url: str) -> MediaInfo:
        opts = {
            **self._base_opts(),
            "skip_download": True,
            # A watch URL copied from YouTube often carries "&list=RD..." (an
            # auto-generated Mix/radio playlist). Without noplaylist yt-dlp
            # resolves every entry of that playlist first, which takes minutes
            # and returns the playlist instead of the video the user meant.
            "noplaylist": True,
            # For a pure playlist URL, list entries without resolving each one,
            # so it's rejected below in seconds instead of hanging.
            "extract_flat": "in_playlist",
            "socket_timeout": _PROBE_TIMEOUT_SECONDS,
        }
        try:
            with self._youtube_dl_factory(opts) as ydl:
                raw = ydl.extract_info(url, download=False)
        except YtDlpDownloadError as error:
            raise self._translate(error) from error
        if raw.get("_type") in ("playlist", "multi_video"):
            raise UnsupportedPlatformError(
                "This is a playlist URL, not a single video. Paste the individual video URLs instead.",
            )
        return self._to_media_info(raw, url)

    def download(
        self,
        request: DownloadRequest,
        on_progress: ProgressCallback,
        cancel_token: CancellationToken,
    ) -> DownloadResult:
        media_info = self.probe(request.url)
        if cancel_token.is_cancelled:
            # Cancel pressed while probing: the progress hook below never ran yet.
            raise DownloadInterruptedError("Download cancelled.")
        audio_format = AudioFormat(request.audio_format)
        ext = audio_format.value if request.audio_only else "mp4"
        target_path = self._filename_planner.plan(request.output_dir, media_info.title, ext)

        def hook(status: dict) -> None:
            if cancel_token.is_cancelled:
                raise _CancelledSignal()
            on_progress(self._to_progress_event(status))

        # outtmpl keeps the literal %(ext)s placeholder rather than our hardcoded
        # extension: without it yt-dlp treats a fixed ".mp4"/".m4a" suffix as part
        # of the base name and appends the real container extension on top of it
        # (observed in practice: "title.mp4.webm"). The postprocessor below is what
        # actually pins the resolved %(ext)s to what target_path already promised.
        opts = {
            **self._base_opts(),
            "outtmpl": f"{target_path.with_suffix('')}.%(ext)s",
            "format": _AUDIO_ONLY_SELECTOR if request.audio_only else _QUALITY_FORMAT_SELECTORS[request.quality],
            "noplaylist": True,
            "progress_hooks": [hook],
            "noprogress": True,
            "socket_timeout": request.timeout_seconds,
            "retries": 0,
            "overwrites": False,
            "windowsfilenames": True,
        }
        if request.audio_only:
            extract_audio = {"key": "FFmpegExtractAudio", "preferredcodec": audio_format.value}
            if audio_format is AudioFormat.MP3:
                # MP3 is a re-encode (YouTube serves AAC/Opus), so pin a solid
                # constant bitrate that every car stereo/player handles.
                extract_audio["preferredquality"] = "192"
            opts["postprocessors"] = [extract_audio]
        else:
            opts["merge_output_format"] = "mp4"
            opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

        on_progress(ProgressEvent(status=ProgressStatus.STARTING, filename=str(target_path)))
        try:
            with self._youtube_dl_factory(opts) as ydl:
                ydl.extract_info(request.url, download=True)
        except _CancelledSignal as error:
            raise DownloadInterruptedError("Download cancelled.", cause=error) from error
        except YtDlpDownloadError as error:
            raise self._translate(error) from error

        on_progress(ProgressEvent(status=ProgressStatus.FINISHED, filename=str(target_path)))
        bytes_downloaded = target_path.stat().st_size if target_path.exists() else 0
        return DownloadResult(file_path=target_path, media_info=media_info, bytes_downloaded=bytes_downloaded)

    def _to_media_info(self, raw: dict, url: str) -> MediaInfo:
        formats = tuple(
            MediaFormat(
                format_id=f.get("format_id", ""),
                ext=f.get("ext", ""),
                resolution=f.get("resolution"),
                is_audio_only=f.get("vcodec") == "none",
            )
            for f in raw.get("formats", []) or []
        )
        return MediaInfo(
            url=url,
            title=raw.get("title") or "download",
            extractor=raw.get("extractor") or "unknown",
            duration_seconds=raw.get("duration"),
            formats=formats,
        )

    def _to_progress_event(self, status: dict) -> ProgressEvent:
        mapped_status = _PROGRESS_STATUS_MAP.get(status.get("status"), ProgressStatus.DOWNLOADING)
        return ProgressEvent(
            status=mapped_status,
            filename=status.get("filename"),
            downloaded_bytes=status.get("downloaded_bytes"),
            total_bytes=status.get("total_bytes") or status.get("total_bytes_estimate"),
            speed_bps=status.get("speed"),
            eta_seconds=status.get("eta"),
        )

    def _translate(self, error: YtDlpDownloadError) -> DownloadError:
        lowered = str(error).lower()
        if "unsupported url" in lowered:
            return UnsupportedPlatformError("This URL is not supported by any known platform.", cause=error)
        if "private video" in lowered or "sign in" in lowered:
            return PrivateContentError("This content is private or requires sign-in.", cause=error)
        if "could not copy" in lowered and "cookie" in lowered:
            return PrivateContentError(
                "Could not read cookies from your browser: it must be fully closed (including any "
                "background/tray processes) for --cookies-from-browser to read its cookie database. "
                "Close it completely and try again, or use --cookies-file with a manually exported "
                "cookies.txt instead.",
                cause=error,
            )
        if "failed to decrypt" in lowered and "dpapi" in lowered:
            return PrivateContentError(
                "Your browser's cookies could not be decrypted (recent Chrome/Edge versions use "
                "extra OS-level protection yt-dlp cannot always unlock). Export a cookies.txt with a "
                "browser extension (e.g. 'Get cookies.txt LOCALLY') and use --cookies-file instead — "
                "it does not depend on decrypting the browser's cookie database.",
                cause=error,
            )
        if "empty media response" in lowered or "cookiesfrombrowser" in lowered:
            return PrivateContentError(
                "This content requires an authenticated session to access. "
                "Re-run with --cookies-from-browser <browser> or --cookies-file <path>.",
                cause=error,
            )
        if "video unavailable" in lowered or "has been removed" in lowered:
            return VideoUnavailableError("This video is unavailable.", cause=error)
        if "requested format is not available" in lowered:
            return FormatUnavailableError(
                "The requested quality/format is not available for this video.", cause=error
            )
        if "timed out" in lowered or "timeout" in lowered:
            return DownloadTimeoutError("The connection timed out.", cause=error)
        if "urlopen error" in lowered or "connection" in lowered or "network" in lowered:
            return NetworkError("A network error occurred.", cause=error)
        return DownloadError("The download failed unexpectedly.", cause=error)

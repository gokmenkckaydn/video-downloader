from __future__ import annotations

import pytest
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from video_downloader.adapters.ytdlp_adapter import YtDlpAdapter
from video_downloader.core.errors import (
    DownloadInterruptedError,
    NetworkError,
    PrivateContentError,
    UnsupportedPlatformError,
    VideoUnavailableError,
)
from video_downloader.core.models import DownloadRequest, ProgressStatus, Quality
from video_downloader.core.ports import CancellationToken


class _FakeYoutubeDL:
    def __init__(self, opts, *, info=None, error=None, progress_events=None):
        self.opts = opts
        self._info = info
        self._error = error
        self._progress_events = progress_events or []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download):
        for event in self._progress_events:
            for hook in self.opts.get("progress_hooks", []):
                hook(event)
        if self._error is not None:
            raise self._error
        return self._info


SAMPLE_INFO = {
    "title": "Sample Video",
    "extractor": "youtube",
    "duration": 120,
    "formats": [
        {"format_id": "137", "ext": "mp4", "resolution": "1080p", "vcodec": "avc1"},
        {"format_id": "140", "ext": "m4a", "resolution": None, "vcodec": "none"},
    ],
}


def test_probe_maps_raw_info_to_media_info():
    factory = lambda opts: _FakeYoutubeDL(opts, info=SAMPLE_INFO)
    adapter = YtDlpAdapter(youtube_dl_factory=factory)

    media_info = adapter.probe("https://example.com/video")

    assert media_info.title == "Sample Video"
    assert media_info.extractor == "youtube"
    assert media_info.duration_seconds == 120
    assert len(media_info.formats) == 2
    assert media_info.formats[1].is_audio_only is True


def test_download_reports_progress_and_returns_result(tmp_path):
    events = [
        {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100},
        {"status": "finished"},
    ]
    factory = lambda opts: _FakeYoutubeDL(opts, info=SAMPLE_INFO, progress_events=events)
    adapter = YtDlpAdapter(youtube_dl_factory=factory)
    seen = []

    request = DownloadRequest(url="https://example.com/video", output_dir=tmp_path, quality=Quality.BEST)
    result = adapter.download(request, on_progress=seen.append, cancel_token=CancellationToken())

    statuses = [event.status for event in seen]
    assert statuses[0] == ProgressStatus.STARTING
    assert ProgressStatus.DOWNLOADING in statuses
    assert ProgressStatus.POSTPROCESSING in statuses
    assert statuses[-1] == ProgressStatus.FINISHED
    assert result.media_info.title == "Sample Video"
    assert result.file_path.parent == tmp_path
    assert result.file_path.name == "Sample Video.mp4"


def test_download_uses_audio_selector_and_extension_when_audio_only(tmp_path):
    factory = lambda opts: _FakeYoutubeDL(opts, info=SAMPLE_INFO)
    adapter = YtDlpAdapter(youtube_dl_factory=factory)

    request = DownloadRequest(url="https://example.com/video", output_dir=tmp_path, audio_only=True)
    result = adapter.download(request, on_progress=lambda e: None, cancel_token=CancellationToken())

    assert result.file_path.suffix == ".m4a"


@pytest.mark.parametrize(
    "message, expected_type",
    [
        ("ERROR: Unsupported URL: foo", UnsupportedPlatformError),
        ("ERROR: Private video. Sign in if you've been invited.", PrivateContentError),
        ("ERROR: Video unavailable", VideoUnavailableError),
        ("ERROR: <urlopen error [Errno 11001] getaddrinfo failed>", NetworkError),
        (
            "ERROR: [Instagram] abc123: Instagram sent an empty media response. "
            "Check if this post is accessible in your browser without being logged-in. "
            "use --cookies-from-browser or --cookies for the authentication.",
            PrivateContentError,
        ),
        (
            "ERROR: ERROR: Could not copy Chrome cookie database. "
            "See https://github.com/yt-dlp/yt-dlp/issues/7271 for more info",
            PrivateContentError,
        ),
        (
            "ERROR: ERROR: Failed to decrypt with DPAPI. "
            "See https://github.com/yt-dlp/yt-dlp/issues/10927 for more info",
            PrivateContentError,
        ),
    ],
)
def test_probe_translates_known_ytdlp_errors(message, expected_type):
    factory = lambda opts: _FakeYoutubeDL(opts, error=YtDlpDownloadError(message))
    adapter = YtDlpAdapter(youtube_dl_factory=factory)

    with pytest.raises(expected_type):
        adapter.probe("https://example.com/video")


def test_probe_passes_cookies_from_browser_to_ytdlp_opts():
    captured = {}

    def factory(opts):
        captured.update(opts)
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    adapter = YtDlpAdapter(youtube_dl_factory=factory, cookies_from_browser="chrome")
    adapter.probe("https://example.com/video")

    assert captured["cookiesfrombrowser"] == ("chrome",)


def test_probe_passes_cookies_file_to_ytdlp_opts(tmp_path):
    captured = {}
    cookies_path = tmp_path / "cookies.txt"

    def factory(opts):
        captured.update(opts)
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    adapter = YtDlpAdapter(youtube_dl_factory=factory, cookies_file=cookies_path)
    adapter.probe("https://example.com/video")

    assert captured["cookiefile"] == str(cookies_path)


def test_probe_attaches_silent_logger_unless_verbose():
    captured = {}

    def factory(opts):
        captured.update(opts)
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    YtDlpAdapter(youtube_dl_factory=factory, verbose=False).probe("https://example.com/video")
    assert "logger" in captured

    captured.clear()
    YtDlpAdapter(youtube_dl_factory=factory, verbose=True).probe("https://example.com/video")
    assert "logger" not in captured


def test_cancellation_raises_download_interrupted(tmp_path):
    events = [{"status": "downloading", "downloaded_bytes": 1, "total_bytes": 100}]
    factory = lambda opts: _FakeYoutubeDL(opts, info=SAMPLE_INFO, progress_events=events)
    adapter = YtDlpAdapter(youtube_dl_factory=factory)
    token = CancellationToken()
    token.cancel()

    request = DownloadRequest(url="https://example.com/video", output_dir=tmp_path)
    with pytest.raises(DownloadInterruptedError):
        adapter.download(request, on_progress=lambda e: None, cancel_token=token)


def test_probe_ignores_playlist_part_of_watch_url():
    seen_opts = []

    def factory(opts):
        seen_opts.append(opts)
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    YtDlpAdapter(youtube_dl_factory=factory).probe(
        "https://www.youtube.com/watch?v=abc&list=RDabc&start_radio=1"
    )

    assert seen_opts[0]["noplaylist"] is True
    assert seen_opts[0]["extract_flat"] == "in_playlist"


def test_probe_rejects_pure_playlist_url():
    playlist = {"_type": "playlist", "title": "Some list", "entries": [{"url": "x"}]}
    adapter = YtDlpAdapter(youtube_dl_factory=lambda opts: _FakeYoutubeDL(opts, info=playlist))

    with pytest.raises(UnsupportedPlatformError, match="playlist"):
        adapter.probe("https://www.youtube.com/playlist?list=PL123")


def test_cancel_during_probe_stops_before_download(tmp_path):
    token = CancellationToken()
    calls = []

    def factory(opts):
        calls.append(opts)
        token.cancel()  # user presses Cancel while info is being fetched
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    adapter = YtDlpAdapter(youtube_dl_factory=factory)
    request = DownloadRequest(url="https://example.com/video", output_dir=tmp_path)

    with pytest.raises(DownloadInterruptedError):
        adapter.download(request, on_progress=lambda e: None, cancel_token=token)
    assert len(calls) == 1  # only the probe ran


def test_download_mp3_sets_codec_bitrate_and_extension(tmp_path):
    from video_downloader.core.models import AudioFormat

    seen_opts = []

    def factory(opts):
        seen_opts.append(opts)
        return _FakeYoutubeDL(opts, info=SAMPLE_INFO)

    request = DownloadRequest(
        url="https://example.com/video", output_dir=tmp_path, audio_only=True, audio_format=AudioFormat.MP3
    )
    result = YtDlpAdapter(youtube_dl_factory=factory).download(
        request, on_progress=lambda e: None, cancel_token=CancellationToken()
    )

    assert result.file_path.suffix == ".mp3"
    extract = seen_opts[-1]["postprocessors"][0]
    assert extract["preferredcodec"] == "mp3"
    assert extract["preferredquality"] == "192"

from __future__ import annotations

import threading
from typing import Protocol

from video_downloader.core.models import (
    DownloadRequest,
    DownloadResult,
    MediaInfo,
    ProgressCallback,
)


class CancellationToken:
    """Checked inside adapter progress hooks to abort mid-download.

    yt-dlp has no native cancel API; raising from inside a progress hook is
    the documented way to unwind out of a running extract_info() call, so
    callers poll `is_cancelled` there instead of relying on thread interrupts.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class MediaProbe(Protocol):
    def probe(self, url: str) -> MediaInfo: ...


class MediaDownloader(Protocol):
    def download(
        self,
        request: DownloadRequest,
        on_progress: ProgressCallback,
        cancel_token: CancellationToken,
    ) -> DownloadResult: ...

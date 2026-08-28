from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from video_downloader.core.errors import DownloadError
from video_downloader.core.models import DownloadRequest
from video_downloader.core.ports import CancellationToken
from video_downloader.core.service import DownloadService


class DownloadWorker(QThread):
    """Runs the blocking DownloadService.start_download off the UI thread.

    Qt widgets aren't safe to touch from a background thread, so progress is
    only ever emitted as a Signal — MainWindow's slots (running on the UI
    thread via the default AutoConnection) are the only place that updates
    widgets from these events.
    """

    progress = Signal(object)  # ProgressEvent
    finished_ok = Signal(object)  # DownloadResult
    failed = Signal(object)  # DownloadError

    def __init__(self, service: DownloadService, request: DownloadRequest, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._request = request
        self.cancel_token = CancellationToken()

    def run(self) -> None:
        try:
            result = self._service.start_download(
                self._request, on_progress=self.progress.emit, cancel_token=self.cancel_token
            )
        except DownloadError as error:
            self.failed.emit(error)
            return
        self.finished_ok.emit(result)


class InfoWorker(QThread):
    """Runs DownloadService.get_media_info off the UI thread for the same reason."""

    succeeded = Signal(object)  # MediaInfo
    failed = Signal(object)  # DownloadError

    def __init__(self, service: DownloadService, url: str, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._url = url

    def run(self) -> None:
        try:
            info = self._service.get_media_info(self._url)
        except DownloadError as error:
            self.failed.emit(error)
            return
        self.succeeded.emit(info)

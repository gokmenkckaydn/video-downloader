from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from video_downloader.core.errors import DownloadError, DownloadInterruptedError
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


class BatchDownloadWorker(QThread):
    """Downloads several requests one after another on a single background thread.

    Each item is independent: a failure is reported via `item_failed` and the
    worker moves on to the next URL. Cancelling aborts the current download and
    skips everything still waiting.
    """

    item_started = Signal(int)  # index
    item_progress = Signal(int, object)  # index, ProgressEvent
    item_finished = Signal(int, object)  # index, DownloadResult
    item_failed = Signal(int, object)  # index, DownloadError
    batch_finished = Signal()

    def __init__(self, service: DownloadService, requests: list[DownloadRequest], parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._requests = list(requests)
        self.cancel_token = CancellationToken()

    def run(self) -> None:
        for index, request in enumerate(self._requests):
            if self.cancel_token.is_cancelled:
                self.item_failed.emit(index, DownloadInterruptedError("Cancelled before start."))
                continue
            self.item_started.emit(index)
            try:
                result = self._service.start_download(
                    request,
                    on_progress=lambda event, i=index: self.item_progress.emit(i, event),
                    cancel_token=self.cancel_token,
                )
            except DownloadError as error:
                self.item_failed.emit(index, error)
                continue
            except Exception as error:  # one broken URL must not stop the rest of the batch
                self.item_failed.emit(index, DownloadError(f"Unexpected error: {error}", cause=error))
                continue
            self.item_finished.emit(index, result)
        self.batch_finished.emit()

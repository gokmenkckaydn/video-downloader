from __future__ import annotations

from video_downloader.core.errors import NetworkError
from video_downloader.core.models import DownloadRequest, DownloadResult, MediaInfo
from video_downloader.gui.download_worker import DownloadWorker, InfoWorker


class _FakeService:
    def __init__(self, *, result=None, error=None, info=None):
        self._result = result
        self._error = error
        self._info = info

    def start_download(self, request, on_progress, cancel_token=None):
        if self._error is not None:
            raise self._error
        return self._result

    def get_media_info(self, url):
        if self._error is not None:
            raise self._error
        return self._info


def _sample_result(tmp_path):
    info = MediaInfo(url="https://example.com", title="Title", extractor="fake", duration_seconds=1)
    return DownloadResult(file_path=tmp_path / "video.mp4", media_info=info, bytes_downloaded=10)


def test_download_worker_emits_finished_ok_on_success(tmp_path):
    result = _sample_result(tmp_path)
    service = _FakeService(result=result)
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    worker = DownloadWorker(service, request)

    finished = []
    failed = []
    worker.finished_ok.connect(finished.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert finished == [result]
    assert failed == []


def test_download_worker_emits_failed_on_error(tmp_path):
    error = NetworkError("boom")
    service = _FakeService(error=error)
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    worker = DownloadWorker(service, request)

    finished = []
    failed = []
    worker.finished_ok.connect(finished.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert finished == []
    assert failed == [error]


def test_download_worker_starts_with_uncancelled_token(tmp_path):
    service = _FakeService(result=_sample_result(tmp_path))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    worker = DownloadWorker(service, request)

    assert worker.cancel_token.is_cancelled is False


def test_info_worker_emits_succeeded_on_success():
    info = MediaInfo(url="https://example.com", title="Title", extractor="fake", duration_seconds=1)
    service = _FakeService(info=info)
    worker = InfoWorker(service, "https://example.com")

    succeeded = []
    failed = []
    worker.succeeded.connect(succeeded.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert succeeded == [info]
    assert failed == []


def test_info_worker_emits_failed_on_error():
    error = NetworkError("boom")
    service = _FakeService(error=error)
    worker = InfoWorker(service, "https://example.com")

    succeeded = []
    failed = []
    worker.succeeded.connect(succeeded.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert succeeded == []
    assert failed == [error]

from __future__ import annotations

from video_downloader.core.errors import DownloadInterruptedError, NetworkError
from video_downloader.core.models import DownloadRequest, DownloadResult, MediaInfo
from video_downloader.gui.download_worker import BatchDownloadWorker


class _SelectiveService:
    def __init__(self, tmp_path, fail_urls=()):
        self._tmp_path = tmp_path
        self._fail_urls = set(fail_urls)
        self.calls = []

    def start_download(self, request, on_progress, cancel_token=None):
        self.calls.append(request.url)
        if request.url in self._fail_urls:
            raise NetworkError(f"boom {request.url}")
        info = MediaInfo(url=request.url, title="Title", extractor="fake", duration_seconds=1)
        return DownloadResult(file_path=self._tmp_path / "video.mp4", media_info=info, bytes_downloaded=10)


def _requests(urls, tmp_path):
    return [DownloadRequest(url=u, output_dir=tmp_path) for u in urls]


def test_batch_worker_downloads_each_url_and_continues_after_failure(tmp_path):
    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
    service = _SelectiveService(tmp_path, fail_urls={urls[1]})
    worker = BatchDownloadWorker(service, _requests(urls, tmp_path))

    finished, failed, done = [], [], []
    worker.item_finished.connect(lambda i, r: finished.append(i))
    worker.item_failed.connect(lambda i, e: failed.append(i))
    worker.batch_finished.connect(lambda: done.append(True))

    worker.run()

    assert service.calls == urls
    assert finished == [0, 2]
    assert failed == [1]
    assert done == [True]


def test_batch_worker_skips_remaining_after_cancel(tmp_path):
    urls = ["https://example.com/1", "https://example.com/2"]
    service = _SelectiveService(tmp_path)
    worker = BatchDownloadWorker(service, _requests(urls, tmp_path))
    worker.item_finished.connect(lambda i, r: worker.cancel_token.cancel())
    errors = []
    worker.item_failed.connect(lambda i, e: errors.append((i, e)))

    worker.run()

    assert service.calls == [urls[0]]
    assert [i for i, _ in errors] == [1]
    assert isinstance(errors[0][1], DownloadInterruptedError)

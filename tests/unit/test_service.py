from __future__ import annotations

from pathlib import Path

import pytest

from video_downloader.core.errors import InsufficientDiskSpaceError, NetworkError
from video_downloader.core.models import (
    DownloadRequest,
    DownloadResult,
    MediaInfo,
    ProgressEvent,
    ProgressStatus,
)
from video_downloader.core.retry import RetryPolicy
from video_downloader.core.service import DownloadService


class _FakeDownloader:
    def __init__(self, *, result=None, errors_then_result=None):
        self.calls = 0
        self._result = result
        self._errors_then_result = errors_then_result or []

    def probe(self, url):
        return MediaInfo(url=url, title="Fake Title", extractor="fake", duration_seconds=10)

    def download(self, request, on_progress, cancel_token):
        self.calls += 1
        on_progress(ProgressEvent(status=ProgressStatus.STARTING))
        if self.calls <= len(self._errors_then_result):
            raise self._errors_then_result[self.calls - 1]
        return self._result


def _make_result(directory: Path) -> DownloadResult:
    info = MediaInfo(url="https://example.com", title="Fake Title", extractor="fake", duration_seconds=10)
    return DownloadResult(file_path=directory / "video.mp4", media_info=info, bytes_downloaded=1024)


def test_start_download_forwards_progress_and_returns_result(tmp_path, monkeypatch):
    monkeypatch.setattr("video_downloader.core.service.ensure_free_space", lambda *a, **k: None)
    result_obj = _make_result(tmp_path)
    downloader = _FakeDownloader(result=result_obj)
    service = DownloadService(downloader=downloader)
    seen = []

    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    result = service.start_download(request, on_progress=seen.append)

    assert result is result_obj
    assert len(seen) == 1
    assert seen[0].status == ProgressStatus.STARTING


def test_start_download_creates_missing_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("video_downloader.core.service.ensure_free_space", lambda *a, **k: None)
    target_dir = tmp_path / "nested" / "downloads"
    downloader = _FakeDownloader(result=_make_result(target_dir))
    service = DownloadService(downloader=downloader)

    request = DownloadRequest(url="https://example.com", output_dir=target_dir)
    service.start_download(request, on_progress=lambda e: None)

    assert target_dir.is_dir()


def test_start_download_raises_before_calling_downloader_when_disk_full(tmp_path, monkeypatch):
    def _raise_disk_full(*args, **kwargs):
        raise InsufficientDiskSpaceError("no space")

    monkeypatch.setattr("video_downloader.core.service.ensure_free_space", _raise_disk_full)
    downloader = _FakeDownloader(result=_make_result(tmp_path))
    service = DownloadService(downloader=downloader)

    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    with pytest.raises(InsufficientDiskSpaceError):
        service.start_download(request, on_progress=lambda e: None)

    assert downloader.calls == 0


def test_start_download_retries_network_errors_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("video_downloader.core.service.ensure_free_space", lambda *a, **k: None)
    result_obj = _make_result(tmp_path)
    downloader = _FakeDownloader(result=result_obj, errors_then_result=[NetworkError("boom")])
    service = DownloadService(
        downloader=downloader,
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0, backoff_multiplier=1),
    )

    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)
    result = service.start_download(request, on_progress=lambda e: None)

    assert result is result_obj
    assert downloader.calls == 2


def test_get_media_info_delegates_to_probe(tmp_path):
    downloader = _FakeDownloader(result=_make_result(tmp_path))
    service = DownloadService(downloader=downloader)

    info = service.get_media_info("https://example.com/video")

    assert info.title == "Fake Title"

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from video_downloader.core.errors import VideoUnavailableError
from video_downloader.core.models import DownloadResult, MediaInfo, ProgressEvent, ProgressStatus
from video_downloader.web.main import create_app


class _FakeDownloader:
    def __init__(self, *, info=None, result=None, error=None, events=None):
        self._info = info
        self._result = result
        self._error = error
        self._events = events or []

    def probe(self, url):
        if self._error is not None:
            raise self._error
        return self._info

    def download(self, request, on_progress, cancel_token):
        for event in self._events:
            on_progress(event)
        if self._error is not None:
            raise self._error
        return self._result


def _sample_info():
    return MediaInfo(url="https://example.com/video", title="Sample", extractor="fake", duration_seconds=42)


def test_media_info_endpoint_returns_info():
    app = create_app(downloader=_FakeDownloader(info=_sample_info()))
    client = TestClient(app)

    resp = client.get("/media-info", params={"url": "https://example.com/video"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Sample"
    assert body["extractor"] == "fake"


def test_media_info_endpoint_rejects_invalid_url():
    app = create_app(downloader=_FakeDownloader(info=_sample_info()))
    client = TestClient(app)

    resp = client.get("/media-info", params={"url": "not-a-url"})

    assert resp.status_code == 400


def test_media_info_endpoint_returns_400_on_domain_error():
    app = create_app(downloader=_FakeDownloader(error=VideoUnavailableError("gone")))
    client = TestClient(app)

    resp = client.get("/media-info", params={"url": "https://example.com/video"})

    assert resp.status_code == 400
    assert "gone" in resp.json()["detail"]


def test_start_download_returns_job_id_and_completes(tmp_path):
    info = _sample_info()
    result = DownloadResult(file_path=tmp_path / "video.mp4", media_info=info, bytes_downloaded=100)
    app = create_app(downloader=_FakeDownloader(info=info, result=result))
    client = TestClient(app)

    resp = client.post("/downloads", json={"url": "https://example.com/video", "quality": "best"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    deadline = time.time() + 2
    status = None
    while time.time() < deadline:
        status = client.get(f"/downloads/{job_id}").json()
        if status["status"] in ("finished", "failed", "cancelled"):
            break
        time.sleep(0.05)

    assert status["status"] == "finished"
    assert status["file_path"] == str(result.file_path)


def test_start_download_rejects_invalid_url():
    app = create_app(downloader=_FakeDownloader(info=_sample_info()))
    client = TestClient(app)

    resp = client.post("/downloads", json={"url": "not-a-url"})

    assert resp.status_code == 400


def test_get_status_returns_404_for_unknown_job():
    app = create_app(downloader=_FakeDownloader(info=_sample_info()))
    client = TestClient(app)

    resp = client.get("/downloads/nonexistent")

    assert resp.status_code == 404


def test_cancel_returns_404_for_unknown_job():
    app = create_app(downloader=_FakeDownloader(info=_sample_info()))
    client = TestClient(app)

    resp = client.post("/downloads/nonexistent/cancel")

    assert resp.status_code == 404


def test_events_endpoint_streams_progress_then_done(tmp_path):
    info = _sample_info()
    result = DownloadResult(file_path=tmp_path / "video.mp4", media_info=info, bytes_downloaded=100)
    events = [
        ProgressEvent(status=ProgressStatus.STARTING),
        ProgressEvent(status=ProgressStatus.DOWNLOADING, downloaded_bytes=50, total_bytes=100),
    ]
    app = create_app(downloader=_FakeDownloader(info=info, result=result, events=events))
    client = TestClient(app)

    resp = client.post("/downloads", json={"url": "https://example.com/video"})
    job_id = resp.json()["job_id"]

    with client.stream("GET", f"/downloads/{job_id}/events") as stream:
        body = "".join(stream.iter_text())

    assert "downloading" in body
    assert "event: done" in body

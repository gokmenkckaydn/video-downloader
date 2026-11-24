from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from video_downloader.core.models import DownloadResult, MediaInfo
from video_downloader.web.main import create_app


class _FakeDownloader:
    def __init__(self):
        self.urls = []

    def probe(self, url):
        return MediaInfo(url=url, title="Sample", extractor="fake", duration_seconds=1)

    def download(self, request, on_progress, cancel_token):
        self.urls.append(request.url)
        info = self.probe(request.url)
        return DownloadResult(file_path=Path("out/video.mp4"), media_info=info, bytes_downloaded=1)


def _wait_for(client, job_id, wanted="finished"):
    status = None
    for _ in range(100):
        status = client.get(f"/downloads/{job_id}").json()["status"]
        if status == wanted:
            break
        time.sleep(0.02)
    return status


def test_batch_endpoint_starts_one_job_per_glued_url(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_DOWNLOADER_OUTPUT_DIR", str(tmp_path))
    downloader = _FakeDownloader()
    client = TestClient(create_app(downloader=downloader))

    text = "https://example.com/ahttps://example.com/b\nhttps://example.com/c www.nope.com/x"
    resp = client.post("/downloads/batch", json={"text": text})

    assert resp.status_code == 200
    items = resp.json()["items"]
    started = [i for i in items if i["job_id"]]
    assert [i["url"] for i in started] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert [i["status"] for i in items if not i["job_id"]] == ["invalid"]
    for item in started:
        assert _wait_for(client, item["job_id"]) == "finished"
    assert sorted(downloader.urls) == [i["url"] for i in started]


def test_batch_endpoint_rejects_text_without_urls():
    client = TestClient(create_app(downloader=_FakeDownloader()))

    resp = client.post("/downloads/batch", json={"text": "hello world"})

    assert resp.status_code == 400

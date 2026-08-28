from __future__ import annotations

import time

from video_downloader.core.errors import DownloadInterruptedError, NetworkError
from video_downloader.core.models import DownloadRequest, DownloadResult, MediaInfo, ProgressEvent, ProgressStatus
from video_downloader.web.jobs import DownloadJobManager, JobState


class _FakeService:
    def __init__(self, *, result=None, error=None, emit_events=None, delay=0.0):
        self._result = result
        self._error = error
        self._emit_events = emit_events or []
        self._delay = delay

    def start_download(self, request, on_progress, cancel_token=None):
        for event in self._emit_events:
            on_progress(event)
        if self._delay:
            time.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self._result


def _sample_result(tmp_path):
    info = MediaInfo(url="https://example.com", title="Title", extractor="fake", duration_seconds=1)
    return DownloadResult(file_path=tmp_path / "video.mp4", media_info=info, bytes_downloaded=10)


def _drain_until_done(record, timeout=2.0):
    deadline = time.time() + timeout
    while record.state.name not in ("FINISHED", "FAILED", "CANCELLED") and time.time() < deadline:
        try:
            record.events.get(timeout=0.5)
        except Exception:
            pass


def test_start_returns_job_id_and_eventually_finishes(tmp_path):
    result = _sample_result(tmp_path)
    manager = DownloadJobManager(service=_FakeService(result=result))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)

    job_id = manager.start(request)
    record = manager.get(job_id)
    assert record is not None

    _drain_until_done(record)

    assert record.state == JobState.FINISHED
    assert record.result is result


def test_failed_job_records_error(tmp_path):
    manager = DownloadJobManager(service=_FakeService(error=NetworkError("boom")))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)

    job_id = manager.start(request)
    record = manager.get(job_id)
    _drain_until_done(record)

    assert record.state == JobState.FAILED
    assert "boom" in record.error.user_message


def test_cancelled_job_marks_state_cancelled(tmp_path):
    manager = DownloadJobManager(service=_FakeService(error=DownloadInterruptedError("cancelled")))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)

    job_id = manager.start(request)
    record = manager.get(job_id)
    _drain_until_done(record)

    assert record.state == JobState.CANCELLED


def test_get_returns_none_for_unknown_job():
    manager = DownloadJobManager(service=_FakeService())
    assert manager.get("nonexistent") is None


def test_cancel_sets_cancel_token_and_returns_true(tmp_path):
    manager = DownloadJobManager(service=_FakeService(result=_sample_result(tmp_path), delay=0.2))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)

    job_id = manager.start(request)
    assert manager.cancel(job_id) is True
    record = manager.get(job_id)
    assert record.cancel_token.is_cancelled is True


def test_cancel_returns_false_for_unknown_job():
    manager = DownloadJobManager(service=_FakeService())
    assert manager.cancel("nonexistent") is False


def test_events_are_pushed_to_queue_in_order(tmp_path):
    events = [
        ProgressEvent(status=ProgressStatus.STARTING),
        ProgressEvent(status=ProgressStatus.DOWNLOADING, downloaded_bytes=5, total_bytes=10),
    ]
    manager = DownloadJobManager(service=_FakeService(result=_sample_result(tmp_path), emit_events=events))
    request = DownloadRequest(url="https://example.com", output_dir=tmp_path)

    job_id = manager.start(request)
    record = manager.get(job_id)

    seen = []
    while True:
        item = record.events.get(timeout=2)
        if item is None:
            break
        seen.append(item)

    assert [e.status for e in seen] == [ProgressStatus.STARTING, ProgressStatus.DOWNLOADING]

from __future__ import annotations

import queue
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict, Optional

from video_downloader.core.errors import DownloadError, DownloadInterruptedError
from video_downloader.core.models import DownloadRequest, DownloadResult, ProgressEvent
from video_downloader.core.ports import CancellationToken
from video_downloader.core.service import DownloadService


class JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobRecord:
    job_id: str
    state: JobState = JobState.QUEUED
    result: Optional[DownloadResult] = None
    error: Optional[DownloadError] = None
    cancel_token: CancellationToken = field(default_factory=CancellationToken)
    # None is the sentinel that ends the SSE stream. One queue per job, so only
    # a single concurrent subscriber is supported per job — fine for a
    # personal-use v1 (one browser tab per download), not fan-out pub/sub.
    events: "queue.Queue[Optional[ProgressEvent]]" = field(default_factory=queue.Queue)


class DownloadJobManager:
    """Runs the blocking DownloadService.start_download on a worker thread so
    an HTTP request can return a job id immediately instead of holding the
    connection open for the whole download. Job state lives only in memory —
    lost on server restart, a deliberate v1 scope decision.
    """

    def __init__(self, service: DownloadService, max_workers: int = 2) -> None:
        self._service = service
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = Lock()

    def start(self, request: DownloadRequest) -> str:
        job_id = uuid.uuid4().hex
        record = JobRecord(job_id=job_id)
        with self._lock:
            self._jobs[job_id] = record
        self._executor.submit(self._run, record, request)
        return job_id

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        record = self.get(job_id)
        if record is None:
            return False
        record.cancel_token.cancel()
        return True

    def _run(self, record: JobRecord, request: DownloadRequest) -> None:
        if record.cancel_token.is_cancelled:
            # Cancelled while still queued (e.g. "Cancel all" on a batch): never start it.
            record.error = DownloadInterruptedError("Cancelled before start.")
            record.state = JobState.CANCELLED
            record.events.put(None)
            return
        record.state = JobState.RUNNING

        def on_progress(event: ProgressEvent) -> None:
            record.events.put(event)

        try:
            record.result = self._service.start_download(
                request, on_progress=on_progress, cancel_token=record.cancel_token
            )
            record.state = JobState.FINISHED
        except DownloadInterruptedError as error:
            record.error = error
            record.state = JobState.CANCELLED
        except DownloadError as error:
            record.error = error
            record.state = JobState.FAILED
        finally:
            record.events.put(None)

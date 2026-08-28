from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError
from video_downloader.core.models import DownloadRequest
from video_downloader.core.validation import validate_url
from video_downloader.web.jobs import DownloadJobManager, JobState
from video_downloader.web.schemas import DownloadRequestBody, JobStatusResponse
from video_downloader.web.security import reject_private_hosts

router = APIRouter(prefix="/downloads", tags=["downloads"])


def get_job_manager() -> DownloadJobManager:
    raise RuntimeError("get_job_manager must be overridden by the app factory (see web/main.py)")


def _to_status_response(job_id: str, record) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job_id,
        status=record.state.value,
        file_path=str(record.result.file_path) if record.result else None,
        error=record.error.user_message if record.error else None,
    )


@router.post("", response_model=JobStatusResponse)
def start_download(body: DownloadRequestBody, manager: DownloadJobManager = Depends(get_job_manager)):
    try:
        url = validate_url(body.url)
        reject_private_hosts(url)
    except DownloadError as error:
        raise HTTPException(status_code=400, detail=error.user_message) from error

    config = AppConfig.from_env()
    request = DownloadRequest(
        url=url,
        output_dir=config.output_dir,
        quality=body.quality,
        audio_only=body.audio_only,
        timeout_seconds=config.timeout_seconds,
    )
    job_id = manager.start(request)
    return JobStatusResponse(job_id=job_id, status=JobState.QUEUED.value)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_download_status(job_id: str, manager: DownloadJobManager = Depends(get_job_manager)):
    record = manager.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_status_response(job_id, record)


@router.post("/{job_id}/cancel")
def cancel_download(job_id: str, manager: DownloadJobManager = Depends(get_job_manager)):
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"cancelled": True}


@router.get("/{job_id}/events")
def stream_download_events(job_id: str, manager: DownloadJobManager = Depends(get_job_manager)):
    record = manager.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    def event_stream():
        while True:
            event = record.events.get()
            if event is None:
                yield "event: done\ndata: {}\n\n"
                break
            payload = {
                "status": event.status.value,
                "downloaded_bytes": event.downloaded_bytes,
                "total_bytes": event.total_bytes,
                "speed_bps": event.speed_bps,
                "eta_seconds": event.eta_seconds,
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

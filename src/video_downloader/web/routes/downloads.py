from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError
from video_downloader.core.models import DownloadRequest
from video_downloader.core.validation import validate_url
from video_downloader.web.jobs import DownloadJobManager, JobState
from video_downloader.core.url_parsing import extract_urls
from video_downloader.web.schemas import (
    BatchDownloadRequestBody,
    BatchDownloadResponse,
    BatchItemResponse,
    DownloadRequestBody,
    JobStatusResponse,
)
from video_downloader.web.security import reject_private_hosts

router = APIRouter(prefix="/downloads", tags=["downloads"])

MAX_BATCH_URLS = 50


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
        audio_format=body.audio_format,
        timeout_seconds=config.timeout_seconds,
    )
    job_id = manager.start(request)
    return JobStatusResponse(job_id=job_id, status=JobState.QUEUED.value)


@router.post("/batch", response_model=BatchDownloadResponse)
def start_batch_download(
    body: BatchDownloadRequestBody, manager: DownloadJobManager = Depends(get_job_manager)
):
    """Start one independent job per URL found in `body.text`.

    Invalid URLs don't fail the whole request — they come back as items with
    status "invalid" so the page can show them next to the ones that started.
    """
    parsed = extract_urls(body.text)
    if not parsed.urls and not parsed.ignored:
        raise HTTPException(status_code=400, detail="No http/https URL found in the input.")
    if len(parsed.urls) > MAX_BATCH_URLS:
        raise HTTPException(
            status_code=400, detail=f"Too many URLs ({len(parsed.urls)}); the limit is {MAX_BATCH_URLS} per batch."
        )

    config = AppConfig.from_env()
    items: list[BatchItemResponse] = [
        BatchItemResponse(url=fragment, status="invalid", error="URLs must start with http:// or https://.")
        for fragment in parsed.ignored
    ]
    for candidate in parsed.urls:
        try:
            url = validate_url(candidate)
            reject_private_hosts(url)
        except DownloadError as error:
            items.append(BatchItemResponse(url=candidate, status="invalid", error=error.user_message))
            continue
        request = DownloadRequest(
            url=url,
            output_dir=config.output_dir,
            quality=body.quality,
            audio_only=body.audio_only,
            audio_format=body.audio_format,
            timeout_seconds=config.timeout_seconds,
        )
        job_id = manager.start(request)
        items.append(BatchItemResponse(url=url, job_id=job_id, status=JobState.QUEUED.value))

    return BatchDownloadResponse(items=items, duplicates=parsed.duplicates)


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

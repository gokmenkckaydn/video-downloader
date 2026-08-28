from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from video_downloader.core.errors import DownloadError
from video_downloader.core.service import DownloadService
from video_downloader.core.validation import validate_url
from video_downloader.web.schemas import MediaInfoResponse
from video_downloader.web.security import reject_private_hosts

router = APIRouter(tags=["media"])


def get_service() -> DownloadService:
    raise RuntimeError("get_service must be overridden by the app factory (see web/main.py)")


@router.get("/media-info", response_model=MediaInfoResponse)
def get_media_info(url: str = Query(...), service: DownloadService = Depends(get_service)):
    try:
        validated_url = validate_url(url)
        reject_private_hosts(validated_url)
        info = service.get_media_info(validated_url)
    except DownloadError as error:
        raise HTTPException(status_code=400, detail=error.user_message) from error
    return MediaInfoResponse(title=info.title, extractor=info.extractor, duration_seconds=info.duration_seconds)

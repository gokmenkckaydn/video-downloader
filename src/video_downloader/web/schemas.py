from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from video_downloader.core.models import Quality


class DownloadRequestBody(BaseModel):
    url: str
    quality: Quality = Quality.BEST
    audio_only: bool = False


class MediaInfoResponse(BaseModel):
    title: str
    extractor: str
    duration_seconds: Optional[float] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    file_path: Optional[str] = None
    error: Optional[str] = None

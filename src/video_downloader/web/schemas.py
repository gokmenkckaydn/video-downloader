from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from video_downloader.core.models import AudioFormat, Quality


class DownloadRequestBody(BaseModel):
    url: str
    quality: Quality = Quality.BEST
    audio_only: bool = False
    audio_format: AudioFormat = AudioFormat.M4A


class MediaInfoResponse(BaseModel):
    title: str
    extractor: str
    duration_seconds: Optional[float] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    file_path: Optional[str] = None
    error: Optional[str] = None


class BatchDownloadRequestBody(BaseModel):
    text: str
    """Free-form text with one or more URLs (newlines, spaces, commas, or glued together)."""
    quality: Quality = Quality.BEST
    audio_only: bool = False
    audio_format: AudioFormat = AudioFormat.M4A


class BatchItemResponse(BaseModel):
    url: str
    job_id: Optional[str] = None
    status: str
    error: Optional[str] = None


class BatchDownloadResponse(BaseModel):
    items: list[BatchItemResponse]
    duplicates: int = 0

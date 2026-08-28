from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class Quality(str, Enum):
    BEST = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"


class ProgressStatus(Enum):
    STARTING = "starting"
    DOWNLOADING = "downloading"
    POSTPROCESSING = "postprocessing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    output_dir: Path
    quality: Quality = Quality.BEST
    audio_only: bool = False
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class MediaFormat:
    format_id: str
    ext: str
    resolution: Optional[str]
    is_audio_only: bool


@dataclass(frozen=True)
class MediaInfo:
    url: str
    title: str
    extractor: str
    duration_seconds: Optional[float]
    formats: tuple[MediaFormat, ...] = ()


@dataclass(frozen=True)
class DownloadResult:
    file_path: Path
    media_info: MediaInfo
    bytes_downloaded: int


@dataclass(frozen=True)
class ProgressEvent:
    status: ProgressStatus
    filename: Optional[str] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[int] = None


ProgressCallback = Callable[[ProgressEvent], None]

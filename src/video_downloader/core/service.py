from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from video_downloader.core.errors import PermissionDeniedError
from video_downloader.core.models import (
    DownloadRequest,
    DownloadResult,
    MediaInfo,
    ProgressCallback,
)
from video_downloader.core.ports import CancellationToken, MediaDownloader, MediaProbe
from video_downloader.core.retry import RetryPolicy, with_retry
from video_downloader.utils.disk import ensure_free_space

_ASSUMED_MIN_FREE_BYTES = 100 * 1024 * 1024  # headroom checked before the real size is known


class DownloadService:
    """The single public entry point core exposes to any UI (CLI, future GUI/web)."""

    def __init__(
        self,
        downloader: MediaDownloader,
        probe: Optional[MediaProbe] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self._downloader = downloader
        self._probe = probe or downloader
        self._retry_policy = retry_policy or RetryPolicy()

    def get_media_info(self, url: str) -> MediaInfo:
        return self._probe.probe(url)

    def start_download(
        self,
        request: DownloadRequest,
        on_progress: ProgressCallback,
        cancel_token: Optional[CancellationToken] = None,
    ) -> DownloadResult:
        token = cancel_token or CancellationToken()
        self._ensure_output_dir_ready(request.output_dir)
        return with_retry(
            lambda: self._downloader.download(request, on_progress, token),
            policy=self._retry_policy,
        )

    def _ensure_output_dir_ready(self, output_dir: Path) -> None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise PermissionDeniedError(
                f"Cannot create or access output directory '{output_dir}'.", cause=error
            ) from error
        if not os.access(output_dir, os.W_OK):
            raise PermissionDeniedError(f"No write permission for output directory '{output_dir}'.")
        ensure_free_space(output_dir, _ASSUMED_MIN_FREE_BYTES)

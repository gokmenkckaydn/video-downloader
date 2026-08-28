from __future__ import annotations

import shutil
from pathlib import Path

from video_downloader.core.errors import InsufficientDiskSpaceError


def ensure_free_space(directory: Path, required_bytes: int) -> None:
    usage = shutil.disk_usage(directory)
    if usage.free < required_bytes:
        raise InsufficientDiskSpaceError(
            f"Not enough free disk space in '{directory}': "
            f"{usage.free} bytes available, {required_bytes} bytes required."
        )

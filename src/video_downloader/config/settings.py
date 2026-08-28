from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ENV_OUTPUT_DIR = "VIDEO_DOWNLOADER_OUTPUT_DIR"
_ENV_TIMEOUT_SECONDS = "VIDEO_DOWNLOADER_TIMEOUT_SECONDS"
_ENV_COOKIES_FROM_BROWSER = "VIDEO_DOWNLOADER_COOKIES_FROM_BROWSER"
_ENV_COOKIES_FILE = "VIDEO_DOWNLOADER_COOKIES_FILE"
_DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class AppConfig:
    output_dir: Path
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    cookies_from_browser: Optional[str] = None
    cookies_file: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "AppConfig":
        default_output_dir = Path.home() / "Downloads" / "video_downloader"
        output_dir = Path(os.environ.get(_ENV_OUTPUT_DIR, str(default_output_dir)))
        timeout_raw = os.environ.get(_ENV_TIMEOUT_SECONDS)
        timeout_seconds = float(timeout_raw) if timeout_raw else _DEFAULT_TIMEOUT_SECONDS
        cookies_from_browser = os.environ.get(_ENV_COOKIES_FROM_BROWSER) or None
        cookies_file_raw = os.environ.get(_ENV_COOKIES_FILE)
        cookies_file = Path(cookies_file_raw) if cookies_file_raw else None
        return cls(
            output_dir=output_dir,
            timeout_seconds=timeout_seconds,
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file,
        )

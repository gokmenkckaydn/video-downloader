from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from video_downloader.core.errors import DownloadError, DownloadTimeoutError, NetworkError

T = TypeVar("T")

_RETRYABLE_ERROR_TYPES = (NetworkError, DownloadTimeoutError)


def is_retryable(error: DownloadError) -> bool:
    return isinstance(error, _RETRYABLE_ERROR_TYPES)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0


def with_retry(
    fn: Callable[[], T],
    policy: RetryPolicy = RetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    delay = policy.initial_delay_seconds
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except DownloadError as error:
            if not is_retryable(error) or attempt == policy.max_attempts:
                raise
            sleep(delay)
            delay *= policy.backoff_multiplier
    raise AssertionError("unreachable: loop always returns or raises")

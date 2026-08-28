from __future__ import annotations

from urllib.parse import urlparse

from video_downloader.core.errors import InvalidUrlError

_ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> str:
    candidate = url.strip()
    if not candidate:
        raise InvalidUrlError("The URL cannot be empty.")
    parsed = urlparse(candidate)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InvalidUrlError(
            f"Unsupported URL scheme '{parsed.scheme or '(none)'}'. Only http/https URLs are supported."
        )
    if not parsed.netloc:
        raise InvalidUrlError("The URL is missing a host.")
    return candidate

"""Turn free-form pasted text into a list of URLs.

Users paste URLs in every shape: one per line, separated by spaces/commas,
or glued together with no separator at all ("https://a/1https://b/2"). This
module is the single place that splits such input, so the CLI, web and GUI
all accept exactly the same formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)

# Characters that commonly wrap or separate pasted URLs but are almost never
# their real first/last character.
_TRIM_CHARS = "\"'`<>,;|"

# A literal "https://" right after these characters is part of the current URL
# (e.g. a redirect parameter "?url=https://..."), not the start of a new one.
_EMBEDDED_PREFIX_CHARS = "="


@dataclass(frozen=True)
class ParsedUrls:
    urls: tuple[str, ...]
    """Unique URLs in the order they appeared."""

    ignored: tuple[str, ...] = ()
    """URL-looking fragments without an http(s) scheme (e.g. "www.site.com/x")."""

    duplicates: int = 0
    """How many repeated URLs were dropped."""


def extract_urls(text: str) -> ParsedUrls:
    urls: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    duplicates = 0

    for token in text.split():
        for piece, has_scheme in _split_glued(token):
            piece = piece.strip(_TRIM_CHARS)
            if not piece:
                continue
            if not has_scheme:
                if _looks_like_url(piece):
                    ignored.append(piece)
                continue
            if piece in seen:
                duplicates += 1
                continue
            seen.add(piece)
            urls.append(piece)

    return ParsedUrls(urls=tuple(urls), ignored=tuple(ignored), duplicates=duplicates)


def _split_glued(token: str) -> list[tuple[str, bool]]:
    starts = [
        match.start()
        for match in _SCHEME_RE.finditer(token)
        if match.start() == 0 or token[match.start() - 1] not in _EMBEDDED_PREFIX_CHARS
    ]
    if not starts:
        return [(token, False)]

    pieces: list[tuple[str, bool]] = []
    if starts[0] > 0:
        pieces.append((token[: starts[0]], False))
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(token)
        pieces.append((token[start:end], True))
    return pieces


def _looks_like_url(fragment: str) -> bool:
    lowered = fragment.lower()
    return lowered.startswith("www.") or ("/" in fragment and "." in fragment)

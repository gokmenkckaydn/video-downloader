from __future__ import annotations

import re
from pathlib import Path

_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MAX_BASENAME_LENGTH = 150


def sanitize_filename(name: str) -> str:
    cleaned = _ILLEGAL_CHARS_RE.sub("_", name)
    cleaned = cleaned.strip(" .")
    if not cleaned:
        cleaned = "download"
    if cleaned.upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    if len(cleaned) > _MAX_BASENAME_LENGTH:
        cleaned = cleaned[:_MAX_BASENAME_LENGTH].rstrip(" .")
    return cleaned


class FilenamePlanner:
    """Resolves a collision-free destination path so downloads never silently overwrite."""

    def plan(self, directory: Path, base_name: str, ext: str) -> Path:
        safe_base = sanitize_filename(base_name)
        ext = ext if ext.startswith(".") else f".{ext}"
        candidate = directory / f"{safe_base}{ext}"
        counter = 1
        while candidate.exists():
            candidate = directory / f"{safe_base} ({counter}){ext}"
            counter += 1
        return candidate

import shutil
from types import SimpleNamespace

import pytest

from video_downloader.core.errors import InsufficientDiskSpaceError
from video_downloader.utils.disk import ensure_free_space


def test_ensure_free_space_raises_when_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(total=100, used=95, free=5))

    with pytest.raises(InsufficientDiskSpaceError):
        ensure_free_space(tmp_path, required_bytes=1000)


def test_ensure_free_space_passes_when_sufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(
        shutil, "disk_usage", lambda path: SimpleNamespace(total=10_000, used=100, free=9_900)
    )

    ensure_free_space(tmp_path, required_bytes=1000)

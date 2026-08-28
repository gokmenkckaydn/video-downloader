from pathlib import Path

from video_downloader.config.settings import AppConfig

_ENV_VARS = (
    "VIDEO_DOWNLOADER_OUTPUT_DIR",
    "VIDEO_DOWNLOADER_TIMEOUT_SECONDS",
    "VIDEO_DOWNLOADER_COOKIES_FROM_BROWSER",
    "VIDEO_DOWNLOADER_COOKIES_FILE",
)


def _clear_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_from_env_uses_defaults_when_unset(monkeypatch):
    _clear_env(monkeypatch)

    config = AppConfig.from_env()

    assert config.output_dir == Path.home() / "Downloads" / "video_downloader"
    assert config.timeout_seconds == 30.0
    assert config.cookies_from_browser is None
    assert config.cookies_file is None


def test_from_env_respects_overrides(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("VIDEO_DOWNLOADER_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("VIDEO_DOWNLOADER_TIMEOUT_SECONDS", "45")

    config = AppConfig.from_env()

    assert config.output_dir == tmp_path
    assert config.timeout_seconds == 45.0


def test_from_env_respects_cookie_overrides(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    cookies_path = tmp_path / "cookies.txt"
    monkeypatch.setenv("VIDEO_DOWNLOADER_COOKIES_FROM_BROWSER", "chrome")
    monkeypatch.setenv("VIDEO_DOWNLOADER_COOKIES_FILE", str(cookies_path))

    config = AppConfig.from_env()

    assert config.cookies_from_browser == "chrome"
    assert config.cookies_file == cookies_path

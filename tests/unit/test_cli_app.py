from __future__ import annotations

from typer.testing import CliRunner

from video_downloader import __version__
from video_downloader.cli import app as cli_app
from video_downloader.core.errors import VideoUnavailableError
from video_downloader.core.models import MediaInfo

runner = CliRunner()


class _FakeService:
    def __init__(self, *, media_info=None, error=None):
        self._media_info = media_info
        self._error = error

    def get_media_info(self, url):
        if self._error is not None:
            raise self._error
        return self._media_info


def test_version_flag_prints_version():
    result = runner.invoke(cli_app.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_info_command_prints_media_info(monkeypatch):
    media_info = MediaInfo(
        url="https://example.com/video",
        title="Sample Video",
        extractor="youtube",
        duration_seconds=90,
    )
    monkeypatch.setattr(cli_app, "_build_service", lambda **kwargs: _FakeService(media_info=media_info))

    result = runner.invoke(cli_app.app, ["info", "https://example.com/video"])

    assert result.exit_code == 0
    assert "Sample Video" in result.stdout
    assert "youtube" in result.stdout


def test_info_command_prints_error_and_exits_nonzero_on_domain_error(monkeypatch):
    monkeypatch.setattr(
        cli_app, "_build_service", lambda **kwargs: _FakeService(error=VideoUnavailableError("gone"))
    )

    result = runner.invoke(cli_app.app, ["info", "https://example.com/video"])

    assert result.exit_code == 1
    assert "gone" in result.stderr


def test_info_command_rejects_invalid_url_before_building_service(monkeypatch):
    called = {"value": False}

    def _fail_if_called(**kwargs):
        called["value"] = True
        raise AssertionError("service should not be built for an invalid URL")

    monkeypatch.setattr(cli_app, "_build_service", _fail_if_called)

    result = runner.invoke(cli_app.app, ["info", "not-a-url"])

    assert result.exit_code == 1
    assert called["value"] is False

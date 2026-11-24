from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from video_downloader.cli import app as cli_app
from video_downloader.core.errors import VideoUnavailableError
from video_downloader.core.models import DownloadResult, MediaInfo

runner = CliRunner()


class _FakeDownloadService:
    def __init__(self, *, fail_urls=()):
        self.downloaded = []
        self._fail_urls = set(fail_urls)

    def start_download(self, request, on_progress, cancel_token=None):
        if request.url in self._fail_urls:
            raise VideoUnavailableError(f"gone: {request.url}")
        self.downloaded.append(request.url)
        info = MediaInfo(url=request.url, title="t", extractor="fake", duration_seconds=1)
        return DownloadResult(
            file_path=Path("out") / f"{len(self.downloaded)}.mp4", media_info=info, bytes_downloaded=1
        )


def test_download_single_url(monkeypatch, tmp_path):
    service = _FakeDownloadService()
    monkeypatch.setattr(cli_app, "_build_service", lambda **kwargs: service)

    result = runner.invoke(cli_app.app, ["download", "https://example.com/a", "-o", str(tmp_path)])

    assert result.exit_code == 0
    assert service.downloaded == ["https://example.com/a"]
    assert "Summary" not in result.stdout


def test_download_glued_urls_in_one_argument(monkeypatch, tmp_path):
    service = _FakeDownloadService()
    monkeypatch.setattr(cli_app, "_build_service", lambda **kwargs: service)

    result = runner.invoke(
        cli_app.app,
        ["download", "https://example.com/ahttps://example.com/bhttps://example.com/c", "-o", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert service.downloaded == ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    assert "3 succeeded, 0 failed" in result.stdout


def test_download_multiple_arguments_continue_after_failure(monkeypatch, tmp_path):
    service = _FakeDownloadService(fail_urls={"https://example.com/b"})
    monkeypatch.setattr(cli_app, "_build_service", lambda **kwargs: service)

    result = runner.invoke(
        cli_app.app,
        [
            "download",
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
            "-o",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert service.downloaded == ["https://example.com/a", "https://example.com/c"]
    assert "2 succeeded, 1 failed" in result.stdout


def test_download_rejects_input_without_any_url(monkeypatch):
    def _fail_if_called(**kwargs):
        raise AssertionError("service should not be built when no URL is valid")

    monkeypatch.setattr(cli_app, "_build_service", _fail_if_called)

    result = runner.invoke(cli_app.app, ["download", "not-a-url"])

    assert result.exit_code == 1


def test_audio_format_mp3_implies_audio_only(monkeypatch, tmp_path):
    from video_downloader.core.models import AudioFormat

    requests = []

    class _Recorder(_FakeDownloadService):
        def start_download(self, request, on_progress, cancel_token=None):
            requests.append(request)
            return super().start_download(request, on_progress, cancel_token)

    monkeypatch.setattr(cli_app, "_build_service", lambda **kwargs: _Recorder())

    result = runner.invoke(
        cli_app.app, ["download", "https://example.com/a", "--audio-format", "mp3", "-o", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert requests[0].audio_only is True
    assert requests[0].audio_format is AudioFormat.MP3

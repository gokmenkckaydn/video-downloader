from __future__ import annotations

import signal
from pathlib import Path
from typing import Optional

import typer

from video_downloader.cli.formatting import ProgressReporter, print_error
from video_downloader.cli.options import (
    AudioOnlyOption,
    CookiesFileOption,
    CookiesFromBrowserOption,
    DebugOption,
    OutputDirOption,
    QualityOption,
    TimeoutOption,
)
from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError
from video_downloader.core.models import DownloadRequest, Quality
from video_downloader.core.ports import CancellationToken
from video_downloader.core.service import DownloadService
from video_downloader.core.validation import validate_url
from video_downloader.utils.logging import configure_logging

app = typer.Typer(add_completion=False, help="Download videos from the command line.")


def _build_service(
    *,
    cookies_from_browser: Optional[str] = None,
    cookies_file: Optional[Path] = None,
    verbose: bool = False,
) -> DownloadService:
    # Imported lazily so importing the CLI module never pulls in yt_dlp until a
    # command actually runs.
    from video_downloader.adapters.ytdlp_adapter import YtDlpAdapter

    return DownloadService(
        downloader=YtDlpAdapter(
            cookies_from_browser=cookies_from_browser,
            cookies_file=cookies_file,
            verbose=verbose,
        )
    )


def _version_callback(value: bool) -> None:
    if value:
        from video_downloader import __version__

        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    pass


@app.command()
def download(
    url: str,
    output: OutputDirOption = None,
    quality: QualityOption = Quality.BEST,
    audio_only: AudioOnlyOption = False,
    timeout: TimeoutOption = 30.0,
    cookies_from_browser: CookiesFromBrowserOption = None,
    cookies_file: CookiesFileOption = None,
    debug: DebugOption = False,
) -> None:
    """Download a video from URL."""
    configure_logging(debug)
    config = AppConfig.from_env()
    output_dir = output or config.output_dir

    try:
        validated_url = validate_url(url)
    except DownloadError as error:
        print_error(error, debug=debug)
        raise typer.Exit(code=1) from error

    request = DownloadRequest(
        url=validated_url,
        output_dir=output_dir,
        quality=quality,
        audio_only=audio_only,
        timeout_seconds=timeout,
    )

    service = _build_service(
        cookies_from_browser=cookies_from_browser or config.cookies_from_browser,
        cookies_file=cookies_file or config.cookies_file,
        verbose=debug,
    )
    cancel_token = CancellationToken()

    def _handle_sigint(signum, frame) -> None:
        cancel_token.cancel()

    previous_handler = signal.signal(signal.SIGINT, _handle_sigint)
    try:
        with ProgressReporter() as report_progress:
            result = service.start_download(request, on_progress=report_progress, cancel_token=cancel_token)
    except DownloadError as error:
        print_error(error, debug=debug)
        raise typer.Exit(code=1) from error
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    typer.secho(f"Done: {result.file_path}", fg=typer.colors.GREEN)


@app.command()
def info(
    url: str,
    cookies_from_browser: CookiesFromBrowserOption = None,
    cookies_file: CookiesFileOption = None,
    debug: DebugOption = False,
) -> None:
    """Show media info for a URL without downloading."""
    configure_logging(debug)
    config = AppConfig.from_env()

    try:
        validated_url = validate_url(url)
    except DownloadError as error:
        print_error(error, debug=debug)
        raise typer.Exit(code=1) from error

    service = _build_service(
        cookies_from_browser=cookies_from_browser or config.cookies_from_browser,
        cookies_file=cookies_file or config.cookies_file,
        verbose=debug,
    )
    try:
        media_info = service.get_media_info(validated_url)
    except DownloadError as error:
        print_error(error, debug=debug)
        raise typer.Exit(code=1) from error

    typer.echo(media_info.title)
    if media_info.duration_seconds:
        typer.echo(f"Duration: {media_info.duration_seconds:.0f}s")
    typer.echo(f"Platform: {media_info.extractor}")

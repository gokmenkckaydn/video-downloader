from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from video_downloader.cli.formatting import ProgressReporter, print_error
from video_downloader.cli.options import (
    AudioFormatOption,
    AudioOnlyOption,
    CookiesFileOption,
    CookiesFromBrowserOption,
    DebugOption,
    OutputDirOption,
    QualityOption,
    TimeoutOption,
)
from video_downloader.config.settings import AppConfig
from video_downloader.core.errors import DownloadError, InvalidUrlError
from video_downloader.core.models import AudioFormat, DownloadRequest, Quality
from video_downloader.core.ports import CancellationToken
from video_downloader.core.service import DownloadService
from video_downloader.core.url_parsing import extract_urls
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
    urls: Annotated[
        List[str],
        typer.Argument(
            help=(
                "One or more URLs. Several URLs can also be pasted as a single argument, "
                "separated by spaces/newlines/commas or glued together (https://a...https://b...)."
            ),
            show_default=False,
        ),
    ],
    output: OutputDirOption = None,
    quality: QualityOption = Quality.BEST,
    audio_only: AudioOnlyOption = False,
    audio_format: AudioFormatOption = None,
    timeout: TimeoutOption = 30.0,
    cookies_from_browser: CookiesFromBrowserOption = None,
    cookies_file: CookiesFileOption = None,
    debug: DebugOption = False,
) -> None:
    """Download one or more videos. Each URL is downloaded separately, one after another."""
    configure_logging(debug)
    config = AppConfig.from_env()
    output_dir = output or config.output_dir
    if audio_format is not None:
        audio_only = True

    parsed = extract_urls(" ".join(urls))
    for fragment in parsed.ignored:
        typer.secho(
            f"Skipped '{fragment}': URLs must start with http:// or https://.", fg=typer.colors.YELLOW, err=True
        )
    if parsed.duplicates:
        typer.secho(f"Skipped {parsed.duplicates} duplicate URL(s).", fg=typer.colors.YELLOW, err=True)

    valid_urls: list[str] = []
    invalid_count = 0
    for candidate in parsed.urls:
        try:
            valid_urls.append(validate_url(candidate))
        except DownloadError as error:
            invalid_count += 1
            typer.secho(f"Skipped '{candidate}': {error.user_message}", fg=typer.colors.YELLOW, err=True)

    if not valid_urls:
        print_error(InvalidUrlError("No valid http/https URL found in the input."), debug=False)
        raise typer.Exit(code=1)

    service = _build_service(
        cookies_from_browser=cookies_from_browser or config.cookies_from_browser,
        cookies_file=cookies_file or config.cookies_file,
        verbose=debug,
    )
    cancel_token = CancellationToken()

    def _handle_sigint(signum, frame) -> None:
        cancel_token.cancel()

    is_batch = len(valid_urls) > 1
    succeeded: list[tuple[str, Path]] = []
    failed: list[tuple[str, str]] = []

    previous_handler = signal.signal(signal.SIGINT, _handle_sigint)
    try:
        for index, url in enumerate(valid_urls, start=1):
            if cancel_token.is_cancelled:
                failed.append((url, "Cancelled before start."))
                continue
            if is_batch:
                typer.secho(f"[{index}/{len(valid_urls)}] {url}", bold=True)
            request = DownloadRequest(
                url=url,
                output_dir=output_dir,
                quality=quality,
                audio_only=audio_only,
                audio_format=audio_format or AudioFormat.M4A,
                timeout_seconds=timeout,
            )
            try:
                with ProgressReporter() as report_progress:
                    result = service.start_download(
                        request, on_progress=report_progress, cancel_token=cancel_token
                    )
            except DownloadError as error:
                print_error(error, debug=debug)
                failed.append((url, error.user_message))
                continue
            typer.secho(f"Done: {result.file_path}", fg=typer.colors.GREEN)
            succeeded.append((url, result.file_path))
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    if is_batch or invalid_count or parsed.ignored:
        typer.echo("")
        typer.secho(
            f"Summary: {len(succeeded)} succeeded, {len(failed)} failed"
            + (f", {invalid_count + len(parsed.ignored)} skipped as invalid" if invalid_count or parsed.ignored else ""),
            bold=True,
        )
        for url, message in failed:
            typer.secho(f"  FAILED  {url} - {message}", fg=typer.colors.RED, err=True)

    if failed or invalid_count or parsed.ignored:
        raise typer.Exit(code=1)


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

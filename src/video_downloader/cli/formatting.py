from __future__ import annotations

import sys
import traceback
from typing import Any, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn

from video_downloader.core.errors import DownloadError
from video_downloader.core.models import ProgressEvent, ProgressStatus

console = Console()

_STATUS_DESCRIPTIONS = {
    ProgressStatus.STARTING: "starting",
    ProgressStatus.DOWNLOADING: "downloading",
    ProgressStatus.POSTPROCESSING: "post-processing",
    ProgressStatus.FINISHED: "finished",
    ProgressStatus.ERROR: "error",
}


def print_error(error: DownloadError, *, debug: bool) -> None:
    # typer.secho (not the rich Console) so CliRunner's stream capture in tests
    # reliably sees it regardless of rich's own terminal/file detection.
    typer.secho(f"Error: {error.user_message}", fg=typer.colors.RED, err=True)
    if debug:
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


class ProgressReporter:
    """Callable progress sink the CLI passes into DownloadService.start_download.

    A future GUI/web UI would supply a different callable against the same
    ProgressEvent contract — this class is the CLI's own rendering, nothing more.
    """

    def __init__(self) -> None:
        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self._task_id: Optional[int] = None

    def __enter__(self) -> "ProgressReporter":
        self._progress.__enter__()
        self._task_id = self._progress.add_task("starting", total=None)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._progress.__exit__(*exc_info)

    def __call__(self, event: ProgressEvent) -> None:
        self._progress.update(
            self._task_id,
            description=_STATUS_DESCRIPTIONS[event.status],
            completed=event.downloaded_bytes,
            total=event.total_bytes,
        )

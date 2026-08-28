from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from video_downloader.core.models import Quality

OutputDirOption = Annotated[
    Optional[Path],
    typer.Option("--output", "-o", help="Directory to save downloaded files into."),
]

QualityOption = Annotated[
    Quality,
    typer.Option("--quality", "-q", help="Preferred video quality."),
]

AudioOnlyOption = Annotated[
    bool,
    typer.Option("--audio-only", help="Download audio only."),
]

TimeoutOption = Annotated[
    float,
    typer.Option("--timeout", help="Network timeout in seconds."),
]

DebugOption = Annotated[
    bool,
    typer.Option("--debug", help="Show full error tracebacks on failure."),
]

CookiesFromBrowserOption = Annotated[
    Optional[str],
    typer.Option(
        "--cookies-from-browser",
        help="Browser to read cookies from for sites that require sign-in (e.g. chrome, firefox, edge).",
    ),
]

CookiesFileOption = Annotated[
    Optional[Path],
    typer.Option("--cookies-file", help="Path to a Netscape-format cookies.txt exported from your browser."),
]

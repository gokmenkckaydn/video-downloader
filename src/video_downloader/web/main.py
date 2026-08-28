from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from video_downloader.core.ports import MediaDownloader
from video_downloader.core.service import DownloadService
from video_downloader.web.jobs import DownloadJobManager
from video_downloader.web.routes import downloads as downloads_routes
from video_downloader.web.routes import media as media_routes

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(downloader: Optional[MediaDownloader] = None) -> FastAPI:
    if downloader is None:
        # Imported lazily so importing this module never pulls in yt_dlp until
        # an app is actually built without an injected fake (mirrors cli/app.py).
        from video_downloader.adapters.ytdlp_adapter import YtDlpAdapter
        from video_downloader.config.settings import AppConfig

        config = AppConfig.from_env()
        downloader = YtDlpAdapter(
            cookies_from_browser=config.cookies_from_browser,
            cookies_file=config.cookies_file,
        )

    service = DownloadService(downloader=downloader)
    manager = DownloadJobManager(service=service)

    app = FastAPI(title="Video Downloader")
    app.dependency_overrides[downloads_routes.get_job_manager] = lambda: manager
    app.dependency_overrides[media_routes.get_service] = lambda: service
    app.include_router(downloads_routes.router)
    app.include_router(media_routes.router)
    if _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
    return app


app = create_app()

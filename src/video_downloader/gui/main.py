from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from video_downloader.config.settings import AppConfig
from video_downloader.core.service import DownloadService
from video_downloader.gui.main_window import MainWindow


def main() -> None:
    # Imported lazily so importing this module never pulls in yt_dlp until the
    # app actually starts (mirrors cli/app.py and web/main.py).
    from video_downloader.adapters.ytdlp_adapter import YtDlpAdapter

    config = AppConfig.from_env()
    downloader = YtDlpAdapter(
        cookies_from_browser=config.cookies_from_browser,
        cookies_file=config.cookies_file,
    )
    service = DownloadService(downloader=downloader)

    app = QApplication(sys.argv)
    window = MainWindow(service=service, config=config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

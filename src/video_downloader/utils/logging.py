from __future__ import annotations

import logging

_LOGGER_NAME = "video_downloader"


def configure_logging(debug: bool) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
    return logger

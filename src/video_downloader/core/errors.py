from __future__ import annotations


class DownloadError(Exception):
    def __init__(self, user_message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        if cause is not None:
            self.__cause__ = cause


class InvalidUrlError(DownloadError):
    pass


class UnsupportedPlatformError(DownloadError):
    pass


class VideoUnavailableError(DownloadError):
    pass


class PrivateContentError(DownloadError):
    pass


class NetworkError(DownloadError):
    pass


class DownloadTimeoutError(DownloadError):
    """Distinct name so it never shadows the builtin TimeoutError."""


class InsufficientDiskSpaceError(DownloadError):
    pass


class PermissionDeniedError(DownloadError):
    pass


class FormatUnavailableError(DownloadError):
    pass


class DownloadInterruptedError(DownloadError):
    pass

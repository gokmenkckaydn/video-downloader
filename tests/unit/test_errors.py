from video_downloader.core.errors import DownloadError, InvalidUrlError


def test_download_error_preserves_user_message():
    err = DownloadError("something went wrong")
    assert err.user_message == "something went wrong"
    assert str(err) == "something went wrong"


def test_download_error_chains_cause():
    original = ValueError("boom")
    err = DownloadError("wrapped", cause=original)
    assert err.__cause__ is original


def test_download_error_without_cause_leaves_cause_unset():
    err = DownloadError("no cause here")
    assert err.__cause__ is None


def test_subclasses_are_download_errors():
    err = InvalidUrlError("bad url")
    assert isinstance(err, DownloadError)
    assert err.user_message == "bad url"

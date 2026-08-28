from video_downloader.core.ports import CancellationToken


def test_cancellation_token_starts_uncancelled():
    token = CancellationToken()
    assert token.is_cancelled is False


def test_cancellation_token_cancel_sets_flag():
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True


def test_cancellation_token_cancel_is_idempotent():
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.is_cancelled is True

import pytest

from video_downloader.core.errors import InvalidUrlError, NetworkError
from video_downloader.core.retry import RetryPolicy, is_retryable, with_retry


def test_is_retryable_true_for_network_error():
    assert is_retryable(NetworkError("boom")) is True


def test_is_retryable_false_for_invalid_url_error():
    assert is_retryable(InvalidUrlError("bad url")) is False


def test_with_retry_returns_result_on_first_success():
    sleeps = []
    result = with_retry(lambda: "ok", sleep=sleeps.append)
    assert result == "ok"
    assert sleeps == []


def test_with_retry_retries_retryable_error_then_succeeds():
    calls = {"count": 0}
    sleeps = []

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise NetworkError("transient")
        return "ok"

    result = with_retry(
        flaky,
        policy=RetryPolicy(max_attempts=3, initial_delay_seconds=1.0, backoff_multiplier=2.0),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert calls["count"] == 3
    assert sleeps == [1.0, 2.0]


def test_with_retry_gives_up_after_max_attempts():
    sleeps = []

    def always_fails():
        raise NetworkError("still down")

    with pytest.raises(NetworkError):
        with_retry(always_fails, policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.1), sleep=sleeps.append)

    assert sleeps == [0.1]


def test_with_retry_does_not_retry_non_retryable_error():
    sleeps = []
    calls = {"count": 0}

    def bad_url():
        calls["count"] += 1
        raise InvalidUrlError("nope")

    with pytest.raises(InvalidUrlError):
        with_retry(bad_url, sleep=sleeps.append)

    assert calls["count"] == 1
    assert sleeps == []

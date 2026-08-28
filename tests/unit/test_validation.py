import pytest

from video_downloader.core.errors import InvalidUrlError
from video_downloader.core.validation import validate_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video",
        "http://example.com/video?id=1",
        "  https://example.com/video  ",
    ],
)
def test_validate_url_accepts_valid_http_urls(url):
    assert validate_url(url).strip() == url.strip()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not a url",
        "ftp://example.com/video",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://",
    ],
)
def test_validate_url_rejects_invalid_urls(url):
    with pytest.raises(InvalidUrlError):
        validate_url(url)

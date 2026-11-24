from __future__ import annotations

from video_downloader.core.url_parsing import extract_urls

A = "https://www.youtube.com/watch?v=abc123"
B = "https://www.instagram.com/reel/XYZ/"
C = "http://vimeo.com/12345"


def test_single_url():
    assert extract_urls(A).urls == (A,)


def test_single_url_with_surrounding_whitespace():
    assert extract_urls(f"   {A}\n").urls == (A,)


def test_glued_urls_are_split():
    assert extract_urls(A + B + C).urls == (A, B, C)


def test_glued_urls_with_trailing_slash_are_split():
    other = B.replace("XYZ", "QQQ")
    assert extract_urls(B + other).urls == (B, other)


def test_newline_space_comma_separators():
    text = f"{A}\n{B}, {C};"
    assert extract_urls(text).urls == (A, B, C)


def test_comma_glued():
    assert extract_urls(f"{A},{B}").urls == (A, B)


def test_twenty_glued_urls():
    urls = [f"https://example.com/video/{i}" for i in range(20)]
    assert extract_urls("".join(urls)).urls == tuple(urls)


def test_embedded_url_in_query_is_not_split():
    url = "https://redirect.example.com/go?url=https://target.example.com/v"
    assert extract_urls(url).urls == (url,)


def test_duplicates_are_dropped_and_counted():
    parsed = extract_urls(A + A + B)
    assert parsed.urls == (A, B)
    assert parsed.duplicates == 1


def test_scheme_is_case_insensitive():
    assert extract_urls("HTTPS://example.com/aHttps://example.com/b").urls == (
        "HTTPS://example.com/a",
        "Https://example.com/b",
    )


def test_schemeless_url_is_reported_as_ignored():
    parsed = extract_urls(f"www.youtube.com/watch?v=1 {A}")
    assert parsed.urls == (A,)
    assert parsed.ignored == ("www.youtube.com/watch?v=1",)


def test_list_numbering_and_quotes_are_ignored_silently():
    parsed = extract_urls(f'1. "{A}"\n2. <{B}>')
    assert parsed.urls == (A, B)
    assert parsed.ignored == ()


def test_empty_text():
    parsed = extract_urls("   \n ")
    assert parsed.urls == ()
    assert parsed.ignored == ()

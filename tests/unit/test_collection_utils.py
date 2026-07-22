"""Tests for the collection utilities: normalization, hashing, retry, parsing."""

from __future__ import annotations

import httpx
import pytest

from app.agents.collector.rss import FeedClient, PermanentFeedError
from app.agents.collector.rss.parser import parse_feed, strip_html
from app.utils.hashing import content_hash, normalize_url, url_hash
from app.utils.retry import RetryError, retry_call

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Example Tech</title>
  <item>
    <title>Rust 2.0 released</title>
    <link>https://example.com/rust-2?utm_source=rss&amp;utm_medium=feed</link>
    <description>&lt;p&gt;A &lt;b&gt;major&lt;/b&gt; release.&lt;/p&gt;</description>
    <author>jane@example.com</author>
    <pubDate>Tue, 14 Jul 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second story</title>
    <link>https://example.com/second</link>
    <pubDate>Wed, 15 Jul 2026 08:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Entry with no link</title>
  </item>
  <item>
    <link>https://example.com/no-title</link>
  </item>
  <item>
    <title>Rust 2.0 released</title>
    <link>https://www.example.com/rust-2/</link>
  </item>
</channel></rss>
"""

ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title>Atom entry</title>
    <link href="https://atom.example.com/post-1"/>
    <updated>2026-07-10T12:00:00Z</updated>
    <summary>Summary text</summary>
  </entry>
</feed>
"""


class TestNormalizeUrl:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("https://Example.com/Post/", "https://example.com/Post"),
            ("https://www.example.com/post", "https://example.com/post"),
            ("http://example.com/post#section", "http://example.com/post"),
            ("https://example.com/p?utm_source=rss&id=7", "https://example.com/p?id=7"),
            ("https://example.com/p?fbclid=abc", "https://example.com/p"),
            ("https://example.com/p?b=2&a=1", "https://example.com/p?a=1&b=2"),
            ("https://example.com:443/p", "https://example.com/p"),
            ("  https://example.com/p  ", "https://example.com/p"),
        ],
    )
    def test_normalization_rules(self, raw: str, expected: str) -> None:
        assert normalize_url(raw) == expected

    def test_cosmetic_variants_share_one_hash(self) -> None:
        variants = [
            "https://example.com/article",
            "https://www.example.com/article/",
            "https://example.com/article?utm_campaign=weekly",
            "https://Example.com/article#top",
        ]
        assert len({url_hash(v) for v in variants}) == 1

    def test_different_articles_differ(self) -> None:
        assert url_hash("https://example.com/a") != url_hash("https://example.com/b")


class TestContentHash:
    def test_ignores_case_and_whitespace(self) -> None:
        assert content_hash("Big  News", "Body   text") == content_hash("big news", "body text")

    def test_distinguishes_different_articles(self) -> None:
        assert content_hash("A", "x") != content_hash("B", "x")

    def test_body_is_optional(self) -> None:
        assert content_hash("Title") == content_hash("title", None)


class TestRetry:
    def test_returns_first_success_without_sleeping(self) -> None:
        delays: list[float] = []
        assert retry_call(lambda: "ok", sleep=delays.append) == "ok"
        assert delays == []

    def test_retries_until_success(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("boom")
            return "ok"

        assert retry_call(flaky, attempts=5, sleep=lambda _: None) == "ok"
        assert calls["n"] == 3

    def test_backoff_grows_and_is_capped(self) -> None:
        delays: list[float] = []

        def always_fail() -> None:
            raise ConnectionError("boom")

        with pytest.raises(RetryError):
            retry_call(
                always_fail,
                attempts=5,
                base_delay=1.0,
                backoff=3.0,
                max_delay=5.0,
                sleep=delays.append,
            )
        assert delays == [1.0, 3.0, 5.0, 5.0]

    def test_raises_retry_error_carrying_last_exception(self) -> None:
        def always_fail() -> None:
            raise ValueError("nope")

        with pytest.raises(RetryError) as exc_info:
            retry_call(always_fail, attempts=2, sleep=lambda _: None)
        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_error, ValueError)

    def test_does_not_retry_unlisted_exceptions(self) -> None:
        calls = {"n": 0}

        def raises_type_error() -> None:
            calls["n"] += 1
            raise TypeError("wrong")

        with pytest.raises(TypeError):
            retry_call(
                raises_type_error, attempts=3, retry_on=(ConnectionError,), sleep=lambda _: None
            )
        assert calls["n"] == 1


class TestStripHtml:
    def test_removes_tags_and_collapses_whitespace(self) -> None:
        assert strip_html("<p>Hello   <b>world</b></p>") == "Hello world"

    def test_empty_input_returns_none(self) -> None:
        assert strip_html("") is None
        assert strip_html(None) is None
        assert strip_html("<p> </p>") is None


class TestParseFeed:
    def test_parses_usable_entries_only(self) -> None:
        parsed = parse_feed(RSS_FEED, source_slug="example")
        # 5 entries: 2 good, 1 no link, 1 no title, 1 duplicate of the first.
        assert len(parsed.items) == 2
        assert parsed.skipped == 3

    def test_strips_tracking_and_html(self) -> None:
        first = parse_feed(RSS_FEED).items[0]
        assert first.url == "https://example.com/rust-2"
        assert first.title == "Rust 2.0 released"
        assert first.summary == "A major release."

    def test_extracts_timezone_aware_dates(self) -> None:
        first = parse_feed(RSS_FEED).items[0]
        assert first.published_at is not None
        assert first.published_at.tzinfo is not None
        assert first.published_at.year == 2026

    def test_handles_atom_format(self) -> None:
        parsed = parse_feed(ATOM_FEED)
        assert len(parsed.items) == 1
        assert parsed.items[0].url == "https://atom.example.com/post-1"
        assert parsed.items[0].summary == "Summary text"

    def test_garbage_input_does_not_raise(self) -> None:
        parsed = parse_feed(b"this is not xml at all")
        assert parsed.items == ()
        assert parsed.malformed is True

    def test_empty_feed_is_handled(self) -> None:
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        assert parse_feed(empty).items == ()


class TestFeedClientStatusHandling:
    """A 4xx must fail immediately; a 5xx must be retried."""

    def _client(self, handler: object, **kwargs: object) -> FeedClient:
        transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
        return FeedClient(client=httpx.Client(transport=transport), **kwargs)  # type: ignore[arg-type]

    def test_permanent_status_is_not_retried(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(403)

        with pytest.raises(PermanentFeedError, match="403"):
            self._client(handler).fetch("https://x.example.com/feed")
        assert calls["n"] == 1

    def test_transient_status_is_retried_then_raises(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        with pytest.raises(RetryError):
            self._client(handler, attempts=3).fetch("https://x.example.com/feed")
        assert calls["n"] == 3

    def test_transient_status_can_recover(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503)
            return httpx.Response(200, content=RSS_FEED, headers={"ETag": 'W/"abc"'})

        response = self._client(handler, attempts=3).fetch("https://x.example.com/feed")
        assert response.status_code == 200
        assert response.etag == 'W/"abc"'

    def test_conditional_headers_are_sent(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update(request.headers)
            return httpx.Response(304)

        response = self._client(handler).fetch(
            "https://x.example.com/feed",
            etag='W/"v1"',
            last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        )
        assert response.not_modified is True
        assert seen["if-none-match"] == 'W/"v1"'
        assert seen["if-modified-since"] == "Mon, 01 Jan 2026 00:00:00 GMT"

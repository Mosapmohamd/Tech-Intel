"""HTTP client for fetching RSS/Atom feeds.

Deliberately separated from parsing: this module knows about HTTP, caching
headers, and retries; it knows nothing about feed formats. That split lets the
parser be tested against fixture bytes with no network at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

from app.utils.retry import retry_call

USER_AGENT = "TechIntelligenceAgent/0.1 (+https://github.com/Mosapmohamd/Tech-Intel)"

#: Status codes worth another attempt. A 403 or 404 will never succeed on
#: retry, so retrying them just wastes the backoff budget on every run.
TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class PermanentFeedError(RuntimeError):
    """A feed returned a status that retrying cannot fix."""


class TransientFeedError(RuntimeError):
    """A feed failed in a way that may succeed on retry."""


#: Errors worth retrying — transport-level problems and transient statuses.
RETRYABLE = (httpx.TransportError, TransientFeedError)


@dataclass(frozen=True, slots=True)
class FeedResponse:
    """The outcome of a single feed fetch."""

    url: str
    status_code: int
    body: bytes
    etag: str | None = None
    last_modified: str | None = None

    @property
    def not_modified(self) -> bool:
        """Whether the server reported the feed is unchanged (HTTP 304)."""
        return self.status_code == 304


class FeedClient:
    """Fetches feed bytes over HTTP with conditional GET support.

    Passing the stored ``ETag`` / ``Last-Modified`` back to the server means an
    unchanged feed costs a 304 with an empty body instead of a full download —
    which matters when polling ~26 feeds every day.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        attempts: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self._attempts = attempts
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, */*",
            },
        )

    def fetch(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FeedResponse:
        """Fetch a feed, honouring cache validators.

        Args:
            url: Feed URL.
            etag: Previously stored ``ETag`` header, if any.
            last_modified: Previously stored ``Last-Modified`` header, if any.

        Returns:
            A :class:`FeedResponse`. Check ``not_modified`` before parsing.

        Raises:
            PermanentFeedError: On a 4xx that retrying cannot fix.
            RetryError: If every retryable attempt fails.
        """
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        def _do_request() -> FeedResponse:
            response = self._client.get(url, headers=headers)
            if response.status_code == 304:
                return FeedResponse(url, 304, b"", etag, last_modified)
            if response.status_code in TRANSIENT_STATUSES:
                raise TransientFeedError(f"HTTP {response.status_code} from {url}")
            if response.status_code >= 400:
                raise PermanentFeedError(f"HTTP {response.status_code} from {url}")
            return FeedResponse(
                url=url,
                status_code=response.status_code,
                body=response.content,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )

        result = retry_call(
            _do_request,
            attempts=self._attempts,
            retry_on=RETRYABLE,
            description=f"fetch {url}",
        )
        logger.debug("Fetched {} → HTTP {} ({} bytes)", url, result.status_code, len(result.body))
        return result

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FeedClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

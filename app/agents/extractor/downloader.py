"""HTTP client for downloading article pages.

Deliberately separate from :mod:`app.agents.collector.rss.client` — that
client speaks conditional GET (ETag / Last-Modified) for feeds, which article
pages have no use for. What *is* shared is imported, not copied: the
browser-like ``User-Agent`` and the transient-status classification, so a
retry policy tuned once for one CDN behaves the same for the other.
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.agents.collector.rss.client import DEFAULT_USER_AGENT, TRANSIENT_STATUSES
from app.utils.retry import retry_call


class PermanentArticleError(RuntimeError):
    """An article page returned a status that retrying cannot fix."""


class TransientArticleError(RuntimeError):
    """An article page failed in a way that may succeed on retry."""


#: Errors worth retrying — transport-level problems and transient statuses.
RETRYABLE = (httpx.TransportError, TransientArticleError)


class ArticleDownloader:
    """Fetches article page HTML over HTTP with retries."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        attempts: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Build an article downloader.

        Args:
            timeout: Per-request timeout in seconds.
            attempts: Total tries per fetch, including the first.
            user_agent: Overrides the default browser-like agent.
            transport: Injectable transport; the client is still built here, so
                the real default headers are exercised. Preferred in tests.
            client: A fully pre-built client. Its own headers are used as-is.
        """
        self._attempts = attempts
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def fetch(self, url: str) -> str:
        """Fetch a page and return its decoded HTML body.

        Raises:
            PermanentArticleError: On a 4xx that retrying cannot fix.
            RetryError: If every retryable attempt fails.
        """

        def _do_request() -> str:
            response = self._client.get(url)
            if response.status_code in TRANSIENT_STATUSES:
                raise TransientArticleError(f"HTTP {response.status_code} from {url}")
            if response.status_code >= 400:
                raise PermanentArticleError(f"HTTP {response.status_code} from {url}")
            return response.text

        result = retry_call(
            _do_request,
            attempts=self._attempts,
            retry_on=RETRYABLE,
            description=f"download {url}",
        )
        logger.debug("Downloaded {} ({} chars)", url, len(result))
        return result

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ArticleDownloader:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

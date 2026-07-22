"""Feed health diagnostics.

Separate from collection on purpose: this probes feeds and reports, but never
writes articles. Useful for validating ``sources.yaml`` after editing it, and
for finding feeds whose URLs have rotted — which happens to a couple of sources
every few months.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.agents.collector.rss import FeedClient, parse_feed
from app.core.config import Settings, get_settings, load_sources


@dataclass(frozen=True, slots=True)
class FeedHealth:
    """The outcome of probing a single feed."""

    slug: str
    feed_url: str
    ok: bool
    items: int = 0
    status_code: int | None = None
    malformed: bool = False
    error: str | None = None

    @property
    def summary(self) -> str:
        """A one-line human-readable verdict."""
        if not self.ok:
            return f"FAIL  {self.error}"
        flag = " (malformed XML, parsed anyway)" if self.malformed else ""
        return f"OK    {self.items} items{flag}"


def check_feeds(*, only: str | None = None, settings: Settings | None = None) -> list[FeedHealth]:
    """Probe every active feed and report whether it is usable.

    Args:
        only: Restrict the probe to one source slug.
        settings: Configuration override, mainly for tests.

    Returns:
        One :class:`FeedHealth` per probed source, in catalogue order.
    """
    settings = settings or get_settings()
    catalogue = load_sources(settings=settings)
    targets = [s for s in catalogue.active() if only is None or s.slug == only]

    results: list[FeedHealth] = []
    with FeedClient(timeout=25.0, attempts=2) as client:
        for config in targets:
            try:
                response = client.fetch(config.feed_url)
                parsed = parse_feed(response.body, source_slug=config.slug)
                results.append(
                    FeedHealth(
                        slug=config.slug,
                        feed_url=config.feed_url,
                        ok=bool(parsed.items),
                        items=len(parsed.items),
                        status_code=response.status_code,
                        malformed=parsed.malformed,
                        error=None if parsed.items else "feed parsed but contained no entries",
                    )
                )
            except Exception as exc:
                logger.warning("Feed check failed for {}: {}", config.slug, exc)
                results.append(
                    FeedHealth(slug=config.slug, feed_url=config.feed_url, ok=False, error=str(exc))
                )
    return results

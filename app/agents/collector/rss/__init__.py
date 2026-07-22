"""RSS feed collection (feedparser + httpx)."""

from app.agents.collector.rss.client import (
    FeedClient,
    FeedResponse,
    PermanentFeedError,
    TransientFeedError,
)
from app.agents.collector.rss.parser import FeedItem, ParsedFeed, parse_feed, strip_html

__all__ = [
    "FeedClient",
    "FeedItem",
    "FeedResponse",
    "ParsedFeed",
    "PermanentFeedError",
    "TransientFeedError",
    "parse_feed",
    "strip_html",
]

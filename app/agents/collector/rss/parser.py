"""RSS/Atom parsing and entry normalization.

feedparser is tolerant of malformed feeds but returns loosely typed dicts with
format-dependent field names. This module converts that into a strict, uniform
:class:`FeedItem` so nothing downstream needs to know whether a feed was RSS
2.0, Atom, or something in between.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.utils.hashing import normalize_url, url_hash

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

#: Entry fields that may hold a publication date, most reliable first.
_DATE_FIELDS = ("published_parsed", "updated_parsed", "created_parsed")
#: Entry fields that may hold the feed-provided blurb.
_SUMMARY_FIELDS = ("summary", "description", "subtitle")


class FeedItem(BaseModel):
    """One normalized entry from a feed."""

    model_config = ConfigDict(frozen=True)

    url: str
    url_hash: str
    title: str = Field(min_length=1, max_length=500)
    author: str | None = None
    summary: str | None = None
    published_at: datetime | None = None


class ParsedFeed(BaseModel):
    """The result of parsing one feed document."""

    model_config = ConfigDict(frozen=True)

    items: tuple[FeedItem, ...]
    malformed: bool = False
    skipped: int = 0


def strip_html(value: str | None) -> str | None:
    """Remove tags and collapse whitespace from a feed blurb."""
    if not value:
        return None
    text = _WHITESPACE.sub(" ", _HTML_TAG.sub(" ", value)).strip()
    return text or None


def _to_datetime(parsed: struct_time | None) -> datetime | None:
    """Convert feedparser's ``struct_time`` into a timezone-aware datetime."""
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _extract_published(entry: Any) -> datetime | None:
    """Return the entry's publication time from whichever field carries it."""
    for field in _DATE_FIELDS:
        moment = _to_datetime(entry.get(field))
        if moment is not None:
            return moment
    return None


def _extract_summary(entry: Any) -> str | None:
    """Return the feed-provided blurb, tags stripped."""
    for field in _SUMMARY_FIELDS:
        text = strip_html(entry.get(field))
        if text:
            return text
    contents = entry.get("content") or []
    if contents:
        return strip_html(contents[0].get("value"))
    return None


def _extract_title(entry: Any) -> str | None:
    """Return the entry title, tags stripped and length-capped."""
    title = strip_html(entry.get("title"))
    return title[:500] if title else None


def parse_feed(body: bytes, *, source_slug: str = "unknown") -> ParsedFeed:
    """Parse feed bytes into normalized items.

    Entries missing a link or a title are skipped rather than failing the whole
    feed — one broken entry should never cost us the other twenty.

    Args:
        body: Raw feed document.
        source_slug: Used only for log context.

    Returns:
        A :class:`ParsedFeed` with the usable items and a skip count.
    """
    parsed = feedparser.parse(body)
    malformed = bool(parsed.get("bozo"))
    if malformed:
        logger.warning(
            "Feed {} is not well-formed ({}); parsing what we can",
            source_slug,
            parsed.get("bozo_exception"),
        )

    items: list[FeedItem] = []
    seen_hashes: set[str] = set()
    skipped = 0

    for entry in parsed.get("entries", []):
        link = entry.get("link")
        title = _extract_title(entry)
        if not link or not title:
            skipped += 1
            continue

        try:
            canonical = normalize_url(link)
            identity = url_hash(link)
        except ValueError:
            skipped += 1
            continue

        # Some feeds list the same entry twice; keep the first occurrence.
        if identity in seen_hashes:
            skipped += 1
            continue
        seen_hashes.add(identity)

        items.append(
            FeedItem(
                url=canonical,
                url_hash=identity,
                title=title,
                author=(entry.get("author") or None),
                summary=_extract_summary(entry),
                published_at=_extract_published(entry),
            )
        )

    if skipped:
        logger.debug("Feed {}: skipped {} unusable entries", source_slug, skipped)
    return ParsedFeed(items=tuple(items), malformed=malformed, skipped=skipped)

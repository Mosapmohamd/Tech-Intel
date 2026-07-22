"""URL normalization and content hashing.

Deduplication quality depends almost entirely on normalization: the same
article routinely arrives as ``https://x.com/post?utm_source=rss`` from one
feed and ``http://www.x.com/post/`` from another. Normalizing before hashing
turns those into a single identity.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

#: Query parameters that identify a campaign, not a document.
TRACKING_PREFIXES = ("utm_", "mc_", "pk_", "hsa_", "_hs")
TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "igshid",
        "ref",
        "referrer",
        "source",
        "src",
        "cmpid",
        "campaign",
        "sh",
        "guccounter",
    }
)

_WHITESPACE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Return a canonical form of ``url`` suitable for identity comparison.

    Lowercases the scheme and host, drops ``www.``, removes tracking query
    parameters and fragments, sorts the remaining parameters, and strips a
    trailing slash from the path.
    """
    url = url.strip()
    parts = urlsplit(url)

    scheme = parts.scheme.lower() or "https"
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if (scheme == "https" and host.endswith(":443")) or (scheme == "http" and host.endswith(":80")):
        host = host.rsplit(":", 1)[0]

    path = parts.path.rstrip("/") or "/"

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(kept))

    return urlunsplit((scheme, host, path, query, ""))


def hash_text(value: str) -> str:
    """Return the SHA-256 hex digest of ``value``."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def url_hash(url: str) -> str:
    """Return a stable identity hash for a URL, after normalization."""
    return hash_text(normalize_url(url))


def content_hash(title: str, body: str | None = None) -> str:
    """Return an identity hash for article content.

    Case, punctuation, and whitespace are stripped so that syndicated copies
    with cosmetic differences still collide. Only the first 2000 characters of
    the body are used — enough to identify the article, cheap to compute, and
    resilient to differing footers or ad markup at the end.
    """
    normalized_title = _WHITESPACE.sub(" ", title.casefold()).strip()
    normalized_body = _WHITESPACE.sub(" ", (body or "").casefold()).strip()[:2000]
    return hash_text(f"{normalized_title}|{normalized_body}")

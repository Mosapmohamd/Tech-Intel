"""Cleaning Agent — normalizes raw extracted text before it is stored.

Single responsibility: turn whatever trafilatura hands back into a
consistent, storable string. It knows nothing about HTTP, trafilatura, or
the database.
"""

from __future__ import annotations

import re
import unicodedata

_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """Normalize unicode form, strip control characters, and collapse
    excess blank lines and trailing whitespace.
    """
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _CONTROL_CHARS.sub("", normalized)
    normalized = _TRAILING_SPACE.sub("\n", normalized)
    normalized = _BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()


def count_words(text: str) -> int:
    """Return a whitespace-based word count."""
    return len(text.split())

"""Thin wrapper around trafilatura's main-content extraction.

Isolated behind one function so the rest of the agent never imports
trafilatura directly — if the extraction library is ever swapped, this is the
only file that changes.
"""

from __future__ import annotations

import trafilatura


def extract_content(html: str, *, url: str) -> str | None:
    """Return the main article text from a page's HTML, or ``None`` if
    trafilatura could not identify readable content.
    """
    return trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )

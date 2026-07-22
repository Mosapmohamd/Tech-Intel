"""Loader for the declarative source catalogue (``sources.yaml``).

The YAML file is validated into Pydantic models before it ever reaches the
database, so a typo in a feed URL or an unknown category fails fast with a
readable error instead of silently producing a broken source row.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config.settings import Settings, get_settings
from app.core.models.enums import CategorySlug


class SourceConfig(BaseModel):
    """One RSS source as declared in ``sources.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    feed_url: str = Field(min_length=1, max_length=500)
    site_url: str | None = None
    group: str = "general"
    default_category: str | None = None
    quality_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    is_active: bool = True
    is_trusted: bool = True
    language: str = "en"

    @field_validator("feed_url", "site_url")
    @classmethod
    def _must_be_http(cls, value: str | None) -> str | None:
        """Reject anything that is not an absolute HTTP(S) URL."""
        if value is None:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https:// — got {value!r}")
        return value

    @field_validator("default_category")
    @classmethod
    def _must_be_known_category(cls, value: str | None) -> str | None:
        """Reject categories outside the fixed taxonomy."""
        if value is None:
            return None
        valid = {slug.value for slug in CategorySlug}
        if value not in valid:
            raise ValueError(f"Unknown category {value!r}. Valid: {sorted(valid)}")
        return value

    def to_orm_fields(self) -> dict[str, Any]:
        """Return the keyword arguments accepted by the ``Source`` model."""
        return self.model_dump()


class SourceCatalogue(BaseModel):
    """The full parsed catalogue."""

    model_config = ConfigDict(frozen=True)

    sources: tuple[SourceConfig, ...]

    def active(self) -> tuple[SourceConfig, ...]:
        """Return only the enabled sources."""
        return tuple(source for source in self.sources if source.is_active)

    def by_slug(self, slug: str) -> SourceConfig | None:
        """Look up a source by slug."""
        return next((source for source in self.sources if source.slug == slug), None)


def _flatten(raw: dict[str, Any]) -> list[SourceConfig]:
    """Expand the grouped YAML structure into flat source configs.

    Precedence is explicit: a value set on the source itself wins over the
    group default, which in turn wins over the file-level ``defaults`` block.
    """
    file_defaults: dict[str, Any] = raw.get("defaults") or {}
    groups: dict[str, Any] = raw.get("groups") or {}
    if not groups:
        raise ValueError("sources.yaml contains no 'groups' section")

    configs: list[SourceConfig] = []
    seen: set[str] = set()

    for group_name, group_body in groups.items():
        group_body = group_body or {}
        group_defaults = {k: v for k, v in group_body.items() if k != "sources"}
        for entry in group_body.get("sources") or []:
            merged: dict[str, Any] = {
                **file_defaults,
                **group_defaults,
                **entry,
                "group": group_name,
            }
            config = SourceConfig(**merged)
            if config.slug in seen:
                raise ValueError(f"Duplicate source slug in sources.yaml: {config.slug!r}")
            seen.add(config.slug)
            configs.append(config)

    if not configs:
        raise ValueError("sources.yaml defines no sources")
    return configs


def load_sources(path: Path | None = None, settings: Settings | None = None) -> SourceCatalogue:
    """Read and validate the source catalogue.

    Args:
        path: Explicit catalogue path. Defaults to ``settings.sources_file``.
        settings: Configuration override, mainly for tests.

    Raises:
        FileNotFoundError: If the catalogue file is missing.
        ValueError: If the catalogue is malformed or contains duplicate slugs.
    """
    settings = settings or get_settings()
    path = path or settings.sources_file
    if not path.exists():
        raise FileNotFoundError(f"Source catalogue not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Source catalogue must be a YAML mapping: {path}")

    return SourceCatalogue(sources=tuple(_flatten(raw)))


def _leading_comments(text: str) -> str:
    """Return the comment/blank-line header at the top of a YAML file.

    ``yaml.safe_dump`` cannot round-trip comments, so the documentation header
    in ``sources.yaml`` would be lost every time ``add-source`` runs. Capturing
    and re-attaching it keeps the file self-documenting without pulling in a
    comment-preserving YAML library.
    """
    header: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith("#"):
            break
        header.append(line)
    return "".join(header)


def append_source(
    config: SourceConfig, path: Path | None = None, settings: Settings | None = None
) -> None:
    """Append a new source to the catalogue file, preserving grouping and comments.

    Used by the ``add-source`` CLI command so users never hand-edit YAML.

    Raises:
        ValueError: If the slug already exists in the target group.
    """
    settings = settings or get_settings()
    path = path or settings.sources_file
    original = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(original) or {}
    groups = raw.setdefault("groups", {})
    group = groups.setdefault(config.group, {})
    entries = group.setdefault("sources", [])

    if any(entry.get("slug") == config.slug for entry in entries):
        raise ValueError(f"Source {config.slug!r} already exists in group {config.group!r}")

    entries.append(config.model_dump(exclude={"group"}, exclude_none=True))
    body = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=100, indent=2)
    path.write_text(_leading_comments(original) + body, encoding="utf-8")

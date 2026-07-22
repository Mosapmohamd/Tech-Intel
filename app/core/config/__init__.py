"""Application configuration (pydantic-settings + declarative source catalogue)."""

from app.core.config.loader import (
    SourceCatalogue,
    SourceConfig,
    append_source,
    load_sources,
)
from app.core.config.settings import PROJECT_ROOT, Settings, get_settings

__all__ = [
    "PROJECT_ROOT",
    "Settings",
    "SourceCatalogue",
    "SourceConfig",
    "append_source",
    "get_settings",
    "load_sources",
]

"""Application settings.

All configuration is read from environment variables (or a ``.env`` file)
using the ``TIA_`` prefix. Nothing in this project reads ``os.environ``
directly — everything goes through :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Settings(BaseSettings):
    """Typed, validated application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="TIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # ── Application ───────────────────────────────────────────
    app_name: str = "Tech Intelligence Agent"
    timezone: str = "Africa/Cairo"
    log_level: LogLevel = "INFO"
    log_dir: Path = Path("logs")
    log_retention: str = "30 days"
    log_rotation: str = "10 MB"

    # ── Database ──────────────────────────────────────────────
    database_path: Path = Path("data/tech_intel.db")
    database_echo: bool = False

    # ── Ollama ────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    ollama_timeout_seconds: int = Field(default=180, gt=0)

    # ── Pipeline limits ───────────────────────────────────────
    max_articles_per_source: int = Field(default=20, gt=0)
    max_summary_words: int = Field(default=120, gt=0)
    top_stories_count: int = Field(default=10, gt=0)
    worth_watching_count: int = Field(default=3, gt=0)

    # ── Extraction ────────────────────────────────────────────
    min_extracted_words: int = Field(default=150, gt=0)
    extraction_timeout_seconds: int = Field(default=30, gt=0)
    extraction_attempts: int = Field(default=3, gt=0)
    extraction_batch_size: int = Field(default=50, gt=0)

    # ── Schedule ──────────────────────────────────────────────
    daily_collect_hour: int = Field(default=6, ge=0, le=23)
    weekly_report_day: Weekday = "sun"
    weekly_report_hour: int = Field(default=9, ge=0, le=23)

    # ── Email ─────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_use_tls: bool = True
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # ── Config file locations ─────────────────────────────────
    sources_file: Path = Path("app/core/config/sources.yaml")
    scoring_file: Path = Path("app/core/config/scoring.yaml")

    @field_validator("log_dir", "database_path", "sources_file", "scoring_file")
    @classmethod
    def _resolve_relative(cls, value: Path) -> Path:
        """Anchor relative paths to the project root, not the working directory."""
        return value if value.is_absolute() else PROJECT_ROOT / value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for the SQLite database."""
        return f"sqlite:///{self.database_path}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def email_recipients(self) -> list[str]:
        """Recipient list parsed from the comma-separated ``TIA_EMAIL_TO``."""
        return [addr.strip() for addr in self.email_to.split(",") if addr.strip()]

    def ensure_directories(self) -> None:
        """Create the directories the application writes to."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()

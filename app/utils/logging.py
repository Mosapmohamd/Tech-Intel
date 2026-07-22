"""Centralized logging configuration built on loguru.

Call :func:`setup_logging` once at process start (CLI entry point).
Every other module simply does ``from loguru import logger``.
"""

from __future__ import annotations

import sys

from loguru import logger

from app.core.config import Settings, get_settings

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"

_configured = False


def setup_logging(settings: Settings | None = None, *, force: bool = False) -> None:
    """Configure console and rotating file sinks.

    Args:
        settings: Configuration to use. Defaults to the global settings.
        force: Reconfigure even if logging was already set up.
    """
    global _configured
    if _configured and not force:
        return

    settings = settings or get_settings()
    settings.ensure_directories()

    logger.remove()
    logger.add(sys.stderr, level=settings.log_level, format=_CONSOLE_FORMAT, colorize=True)
    logger.add(
        settings.log_dir / "tia_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        format=_FILE_FORMAT,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        settings.log_dir / "errors.log",
        level="ERROR",
        format=_FILE_FORMAT,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,
    )
    _configured = True

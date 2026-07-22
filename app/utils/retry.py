"""Retry helper with exponential backoff.

Written as a small standalone utility rather than pulling in tenacity: the
policy needed here is simple, and keeping it local makes it trivial to unit
test with a fake sleep function.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from loguru import logger


class RetryError(RuntimeError):
    """Raised when every retry attempt has been exhausted."""

    def __init__(self, attempts: int, last_error: Exception) -> None:
        super().__init__(f"Failed after {attempts} attempt(s): {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def retry_call[T](
    func: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    description: str = "operation",
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``func``, retrying on failure with exponential backoff.

    Args:
        func: Zero-argument callable to invoke.
        attempts: Total number of tries, including the first.
        base_delay: Delay before the second attempt, in seconds.
        backoff: Multiplier applied to the delay after each failure.
        max_delay: Ceiling on the delay between attempts.
        retry_on: Exception types that should trigger a retry.
        description: Label used in log messages.
        sleep: Injectable sleep function, so tests run instantly.

    Returns:
        Whatever ``func`` returns on its first successful call.

    Raises:
        RetryError: If every attempt fails.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    delay = base_delay
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except retry_on as exc:  # noqa: PERF203 — retry loop needs the try inside
            last_error = exc
            if attempt == attempts:
                break
            logger.warning(
                "{} failed (attempt {}/{}): {} — retrying in {:.1f}s",
                description,
                attempt,
                attempts,
                exc,
                delay,
            )
            sleep(delay)
            delay = min(delay * backoff, max_delay)

    assert last_error is not None  # noqa: S101 — unreachable unless attempts < 1
    logger.error("{} failed after {} attempt(s): {}", description, attempts, last_error)
    raise RetryError(attempts, last_error)

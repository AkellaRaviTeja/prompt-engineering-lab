"""Retries with exponential backoff and full jitter.

A call is retried only when it raises `Transient`: a rate limit (429), a server error (5xx), a
timeout or a dropped connection. Anything else (a bad request, a missing model, a schema the
provider rejects) fails at once, because sending it again cannot help.

The wait before attempt n+1 is a random time between 0 and min(cap, base * 2**n): "full jitter",
so a hundred clients that failed together do not all come back together. A provider's
`retry-after` hint, when given, is a floor on that wait.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Transient(Exception):
    """A failure worth retrying. `retry_after` is the provider's hint in seconds, if any."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def backoff(
    attempt: int, base: float, cap: float, rng: Callable[[], float] = random.random
) -> float:
    """Full-jitter wait before retry number `attempt` (0 for the first retry)."""
    return rng() * min(cap, base * 2**attempt)


def call(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    base: float = 1.0,
    cap: float = 30.0,
    sleep: Callable[[float], Any] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> tuple[T, int]:
    """Run fn, retrying Transient failures up to `retries` times. Returns (result, attempts).

    After the last retry the Transient error becomes a SystemExit with its message, so a lesson
    stops with a readable line rather than a traceback.
    """
    for attempt in range(retries + 1):
        try:
            return fn(), attempt + 1
        except Transient as e:
            if attempt == retries:
                raise SystemExit(f"{e} (gave up after {attempt + 1} attempts)") from e
            wait = backoff(attempt, base, cap, rng)
            if e.retry_after is not None:
                wait = max(wait, e.retry_after)
            sleep(wait)
    raise AssertionError("unreachable")

"""Chapter 17 exercise: write the batch runner yourself.

Fill in `run_batch`. Grade it with `make exercise N=17` (offline: the tests use a scripted model).
When every test passes, run the live lesson on your runner: `make lesson N=17 ARGS=--mine`.

Stuck? `make hint N=17`. Start again? `make exercise-reset N=17`.
"""

from __future__ import annotations

import random
import threading  # noqa: F401  (the solution uses it for the retry budget)
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor  # noqa: F401
from typing import Any

from lantern.retry import Transient, backoff  # noqa: F401


def run_batch(
    items: list[dict],
    *,
    chat: Callable[..., Any],
    prompt: Callable[[dict], list[dict]],
    concurrency: int = 1,
    timeout: float = 10.0,
    retries: int = 3,
    base: float = 0.2,
    cap: float = 5.0,
    retry_budget: int | None = None,
    log: Callable[[dict], Any] | None = None,
    sleep: Callable[[float], Any] = time.sleep,
    rng: Callable[[], float] = random.random,
    **options: Any,
) -> list[dict]:
    """Send every item to the model, at most `concurrency` calls at a time.

    Each item becomes one call: `chat(prompt(item), timeout=timeout, **options)`. A call that
    raises `Transient` (a 429, a 5xx, a timeout) is retried up to `retries` times, waiting
    `backoff(attempt, base, cap, rng)` seconds before retry `attempt` (0 for the first), or the
    error's `retry_after` if that is longer. Any other exception fails the item at once.

    `retry_budget`, if set, is the most retries the whole batch may spend. Once it is spent, a
    Transient failure is final: the batch stops adding load to a service that is already failing.

    `log`, if given, is called once per attempt with {"id", "attempt", "outcome", "seconds",
    "error"}, where outcome is "ok", "retry" or "failed".

    Returns one dict per item, in the order of `items`:
        {"id", "ok", "reply", "attempts", "seconds", "error"}
    `seconds` is the item's whole time, waits included; `reply` is None when it failed.
    """
    # TODO 1: a function that handles ONE item: call chat(prompt(item), timeout=timeout,
    #         **options) and return the result dict with ok=True on success.
    # TODO 2: on Transient, retry up to `retries` times. Before retry n (n = 0 first), sleep
    #         backoff(n, base, cap, rng), or e.retry_after if that is longer. Use `sleep`, not
    #         time.sleep, so the tests do not wait.
    # TODO 3: any other exception fails the item at once, with no retry.
    # TODO 4: a retry budget shared by every item (guard it with a lock: items run in threads).
    #         None means no limit. When it is spent, a Transient failure is final.
    # TODO 5: call `log` once per attempt with the outcome "ok", "retry" or "failed".
    # TODO 6: run the items in a ThreadPoolExecutor with max_workers=concurrency, and return
    #         the results in the order of `items` (pool.map keeps the order).
    raise NotImplementedError("TODO 1 to 6: the batch runner")

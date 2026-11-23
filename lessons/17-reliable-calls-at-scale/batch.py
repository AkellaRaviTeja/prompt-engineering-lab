"""Chapter 17: the lesson's own batch runner (bounded concurrency, timeouts, retries, a budget).

run.py uses this one, so a change to practice/ never changes the lesson's numbers without the
change check seeing it. practice/solution.py is the same code, written for the exercise; --mine
uses yours.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from lantern.retry import Transient, backoff


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
    budget_lock = threading.Lock()
    budget = {"left": retry_budget}

    def take_retry() -> bool:
        with budget_lock:
            if budget["left"] is None:
                return True
            if budget["left"] <= 0:
                return False
            budget["left"] -= 1
            return True

    def note(item: dict, attempt: int, outcome: str, t0: float, error: str | None) -> None:
        if log:
            log({"id": item.get("id"), "attempt": attempt, "outcome": outcome,
                 "seconds": time.perf_counter() - t0, "error": error})

    def one(item: dict) -> dict:
        start = time.perf_counter()
        error = None
        for attempt in range(retries + 1):
            t0 = time.perf_counter()
            try:
                r = chat(prompt(item), timeout=timeout, **options)
            except Transient as e:
                error = str(e)
                if attempt == retries or not take_retry():
                    note(item, attempt + 1, "failed", t0, error)
                    return {"id": item.get("id"), "ok": False, "reply": None,
                            "attempts": attempt + 1, "seconds": time.perf_counter() - start,
                            "error": error}
                note(item, attempt + 1, "retry", t0, error)
                wait = backoff(attempt, base, cap, rng)
                if e.retry_after is not None:
                    wait = max(wait, e.retry_after)
                sleep(wait)
                continue
            except Exception as e:  # not worth retrying: a bad request, a bug
                error = f"{type(e).__name__}: {e}"
                note(item, attempt + 1, "failed", t0, error)
                return {"id": item.get("id"), "ok": False, "reply": None,
                        "attempts": attempt + 1, "seconds": time.perf_counter() - start,
                        "error": error}
            note(item, attempt + 1, "ok", t0, None)
            return {"id": item.get("id"), "ok": True, "reply": r, "attempts": attempt + 1,
                    "seconds": time.perf_counter() - start, "error": None}
        raise AssertionError("unreachable")

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return list(pool.map(one, items))

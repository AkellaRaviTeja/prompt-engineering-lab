"""Chapter 17: the batch runner. Each test's first docstring line is what `make exercise` shows."""

import threading
import time

from lantern.retry import Transient
from lantern.testing import Scripted, say

ITEMS = [{"id": f"S{i}", "text": f"message {i}"} for i in range(1, 4)]


def prompt(item):
    return [{"role": "user", "content": item["text"]}]


def go(impl, model, items=ITEMS, **kw):
    waits = []
    kw.setdefault("sleep", waits.append)
    kw.setdefault("rng", lambda: 0.5)
    out = impl.run_batch(items, chat=model, prompt=prompt, **kw)
    return out, waits


def test_every_item_is_sent_once_and_results_keep_their_order(impl):
    """One call per item, with the item's prompt; results come back in input order."""
    model = Scripted([say("logistics"), say("personal"), say("threat")])
    out, _ = go(impl, model)
    assert [r["id"] for r in out] == ["S1", "S2", "S3"], "keep the order of `items`"
    assert all(r["ok"] and r["attempts"] == 1 for r in out), f"every item should pass: {out}"
    assert [r["reply"].text for r in out] == ["logistics", "personal", "threat"]
    sent = [q["messages"][0]["content"] for q in model.requests]
    assert sent == ["message 1", "message 2", "message 3"], "send prompt(item) for each item"


def test_timeout_and_options_reach_every_call(impl):
    """Each call carries the timeout and any extra options (temperature, model...)."""
    model = Scripted([say("logistics")])
    go(impl, model, items=ITEMS[:1], timeout=4.0, temperature=0, max_tokens=4)
    req = model.requests[0]
    assert req.get("timeout") == 4.0, "pass timeout= to chat, so a stuck call is cut off"
    assert req.get("temperature") == 0 and req.get("max_tokens") == 4, "pass **options on"


def test_transient_failures_are_retried_with_full_jitter_backoff(impl):
    """A 429 then a 503 are retried; waits are rng * min(cap, base * 2**n)."""
    model = Scripted([Transient("HTTP 429"), Transient("HTTP 503"), say("threat")])
    out, waits = go(impl, model, items=ITEMS[:1], base=1.0, cap=30.0, rng=lambda: 0.5)
    assert out[0]["ok"] and out[0]["attempts"] == 3, f"two retries, then success: {out[0]}"
    assert waits == [0.5, 1.0], f"waits should be 0.5*1 then 0.5*2, got {waits}"


def test_retry_after_is_a_floor_on_the_wait(impl):
    """A provider's retry-after hint is waited out even when the backoff is shorter."""
    model = Scripted([Transient("HTTP 429", retry_after=7.0), say("logistics")])
    _, waits = go(impl, model, items=ITEMS[:1], base=0.2, cap=5.0)
    assert waits == [7.0], f"wait at least retry_after, got {waits}"


def test_gives_up_after_the_last_retry(impl):
    """An item that keeps failing stops after `retries` retries and is marked failed."""
    model = Scripted([Transient("HTTP 503")] * 3)
    out, waits = go(impl, model, items=ITEMS[:1], retries=2)
    r = out[0]
    assert not r["ok"] and r["reply"] is None, "a failed item has ok False and no reply"
    assert r["attempts"] == 3 and model.calls == 3, f"1 call + 2 retries, got {r['attempts']}"
    assert "503" in (r["error"] or ""), "keep the last error message"
    assert len(waits) == 2, "no wait after the final attempt"


def test_other_errors_are_not_retried(impl):
    """A bad request (not Transient) fails the item at once and the batch goes on."""
    model = Scripted([ValueError("schema rejected"), say("personal")])
    out, waits = go(impl, model, items=ITEMS[:2])
    assert not out[0]["ok"] and out[0]["attempts"] == 1, "do not retry a non-Transient error"
    assert out[1]["ok"], "one failed item must not stop the batch"
    assert waits == [], "nothing to wait for"


def test_retry_budget_caps_retries_across_the_batch(impl):
    """With retry_budget=1, only one retry is spent for the whole batch."""
    model = Scripted([Transient("HTTP 503")] * 6)
    out, _ = go(impl, model, items=ITEMS[:2], retries=3, retry_budget=1)
    assert sum(r["attempts"] for r in out) == 3, (
        f"2 first attempts + 1 retry from the budget, got {[r['attempts'] for r in out]}"
    )
    assert not any(r["ok"] for r in out)


def test_concurrency_is_bounded(impl):
    """No more than `concurrency` calls are in flight at once, and more than one is used."""
    lock, live, peak = threading.Lock(), [0], [0]

    def slow(messages, **kw):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.02)
        with lock:
            live[0] -= 1
        return say("logistics")

    items = [{"id": f"S{i}", "text": "x"} for i in range(8)]
    out = impl.run_batch(items, chat=slow, prompt=prompt, concurrency=3)
    assert all(r["ok"] for r in out)
    assert peak[0] == 3, f"expected exactly 3 calls at once at concurrency 3, saw {peak[0]}"


def test_every_attempt_is_logged(impl):
    """log() gets one event per attempt: retry, then ok."""
    events = []
    model = Scripted([Transient("HTTP 429"), say("threat")])
    go(impl, model, items=ITEMS[:1], log=events.append)
    assert [e["outcome"] for e in events] == ["retry", "ok"], f"got {events}"
    assert [e["attempt"] for e in events] == [1, 2] and events[0]["id"] == "S1"

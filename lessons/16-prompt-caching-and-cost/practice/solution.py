"""Chapter 16 solution: what a run costs, and what in a prompt would break its cache."""

from __future__ import annotations

import json
import re
from typing import Any

# Things that change on every call. Any of them in the fixed part of a prompt moves the point
# where two calls stop matching to the front, and nothing after it can be reused.
VOLATILE = {
    "timestamp": re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?"),
    "clock time": re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b"),
    "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    "request id": re.compile(r"\b(request|req|trace|session)[ _-]?id\b", re.I),
}


def run_cost(records: list[dict], prices: dict[str, dict]) -> dict[str, Any]:
    """USD for a run, from call-log records and a price table (USD per million tokens).

    Each record uses the call log's keys (`lantern.calllog`):
        gen_ai.request.model, gen_ai.usage.input_tokens (every input token, cached or not),
        gen_ai.usage.cache_read.input_tokens, gen_ai.usage.cache_creation.input_tokens,
        gen_ai.usage.output_tokens
    Each price entry has input, output, and optionally cache_read, cache_write (each defaults to
    input when missing) and `over`: {tokens, input, output, cache_read, cache_write}. A request
    whose input tokens exceed over["tokens"] is billed entirely at the `over` prices.

    Returns {"usd": total for priced calls, "calls": priced calls, "unpriced": [models with no
    price, once each, in first-seen order]}. An unpriced call is never counted as free.
    """
    usd, calls, unpriced = 0.0, 0, []
    for r in records:
        model = r["gen_ai.request.model"]
        p = prices.get(model)
        if not p or p.get("input") is None:
            if model not in unpriced:
                unpriced.append(model)
            continue
        total_in = r.get("gen_ai.usage.input_tokens", 0)
        if "over" in p and total_in > p["over"]["tokens"]:
            p = p["over"]
        read = r.get("gen_ai.usage.cache_read.input_tokens", 0)
        write = r.get("gen_ai.usage.cache_creation.input_tokens", 0)
        plain = max(total_in - read - write, 0)
        usd += (
            plain * p["input"]
            + read * p.get("cache_read", p["input"])
            + write * p.get("cache_write", p["input"])
            + r.get("gen_ai.usage.output_tokens", 0) * p["output"]
        ) / 1e6
        calls += 1
    return {"usd": usd, "calls": calls, "unpriced": unpriced}


def cache_breakers(
    messages: list[dict], tools: list[dict] | None = None, previous: dict | None = None
) -> list[str]:
    """What in this request would stop its prefix being reused by the next one.

    The fixed part of a request is the tools and every message before the last user turn (the
    last user turn is the input, which is meant to change). Report, one string each:
      - "<where>: <kind> '<text>'" for each volatile value (VOLATILE) in the fixed part, where
        <where> is "message N" (its index in `messages`) or "tools";
      - "tools: same tools in a different order" when `previous` (an earlier request, as
        {"messages": [...], "tools": [...]}) had the same tool names in another order;
      - "message N: differs from the previous request" for the first fixed message that differs
        from the same position in `previous`, when the tools did not already differ.
    An empty list means nothing was found.
    """
    found: list[str] = []
    last_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)
    fixed = messages[:last_user] if last_user >= 0 else list(messages)
    parts = [(f"message {i}", str(m.get("content", ""))) for i, m in enumerate(fixed)]
    if tools:
        parts.insert(0, ("tools", json.dumps(tools, sort_keys=True)))
    for where, text in parts:
        for kind, pattern in VOLATILE.items():
            for m in pattern.finditer(text):
                found.append(f"{where}: {kind} '{m.group(0)}'")
    if previous is not None:
        names = [t.get("name") for t in tools or []]
        before = [t.get("name") for t in previous.get("tools") or []]
        tools_moved = names != before and sorted(names) == sorted(before)
        if tools_moved:
            found.append("tools: same tools in a different order")
        old = previous.get("messages", [])
        for i, m in enumerate(fixed):
            if not tools_moved and (i >= len(old) or old[i] != m):
                found.append(f"message {i}: differs from the previous request")
                break
    return found

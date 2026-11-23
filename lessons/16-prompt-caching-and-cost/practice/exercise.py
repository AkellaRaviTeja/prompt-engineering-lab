"""Chapter 16 exercise: price a run, and find what would break a prompt's cache.

Fill in `run_cost` and `cache_breakers`. Grade them with `make exercise N=16` (offline, no model).
Then point `run_cost` at your own call log: `.progress/calls.jsonl` holds one record per call
(`lantern.calllog.read()` loads it), and config.yaml's `prices:` is the table.

Stuck? `make hint N=16`. Start again? `make exercise-reset N=16`.
"""

from __future__ import annotations

import json  # noqa: F401  (the solution uses it)
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
    # TODO 1: for each record, look up its model's prices. No entry, or input None: add the
    #         model to `unpriced` (once) and skip the record.
    # TODO 2: if the entry has `over` and the input tokens exceed over["tokens"], use the
    #         `over` prices for the whole request.
    # TODO 3: split the input: cache reads, cache writes, and the rest (input minus both).
    #         Price each part at its own rate, plus output tokens at the output rate.
    # TODO 4: prices are per million tokens. Return {"usd", "calls", "unpriced"}.
    raise NotImplementedError("TODO 1 to 4: run_cost")


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
    # TODO 5: find the last user turn; the fixed part is every message before it.
    # TODO 6: scan the fixed messages (and the tools, as json.dumps(tools, sort_keys=True)) for
    #         every VOLATILE pattern and report each match.
    # TODO 7: with `previous`: report reordered tools, else the first fixed message that differs.
    raise NotImplementedError("TODO 5 to 7: cache_breakers")

"""A log line for every model call: prompt version, model, tokens, cost and latency.

Each call appends one JSON object to `.progress/calls.jsonl` (git ignores it). The keys use the
OpenTelemetry GenAI semantic convention names where one exists, so the same record can be read
next to a trace. Set LANTERN_CALL_LOG to another path, or to an empty string to turn it off.

    {"ts": ..., "chapter": "08", "lantern.prompt.version": "extract-invoice@v2",
     "gen_ai.provider.name": "ollama", "gen_ai.request.model": "qwen3:1.7b",
     "gen_ai.usage.input_tokens": 412, "gen_ai.usage.output_tokens": 96,
     "gen_ai.usage.cache_read.input_tokens": 0, "lantern.cost_usd": 0.0,
     "lantern.latency_s": 3.1, "lantern.attempts": 1, ...}
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lantern.config import ROOT

if TYPE_CHECKING:
    from lantern.llm import Reply


def path() -> Path | None:
    p = os.getenv("LANTERN_CALL_LOG")
    if p == "":
        return None
    return Path(p) if p else ROOT / ".progress" / "calls.jsonl"


def prompt_hash(messages: list[dict[str, Any]], format: Any = None, tools: Any = None) -> str:
    """A version label for a prompt: a hash of the parts that define it, not the input.

    The system prompt, the response schema and the tools define what a prompt does; the user
    turn is the input it runs on. Change the first three and the version changes.
    """
    fixed = [m.get("content") for m in messages if m.get("role") == "system"]
    blob = json.dumps([fixed, format, tools], sort_keys=True, default=str)
    return "auto:" + hashlib.sha256(blob.encode()).hexdigest()[:10]


def record(r: Reply) -> dict[str, Any]:
    from lantern.learn import chapter_of

    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "chapter": chapter_of(),
        "script": Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "",
        "lantern.prompt.version": r.prompt_version,
        "gen_ai.provider.name": r.provider,
        "gen_ai.request.model": r.model,
        "gen_ai.usage.input_tokens": r.prompt_tokens,
        "gen_ai.usage.output_tokens": r.output_tokens,
        "gen_ai.usage.cache_read.input_tokens": r.cached_tokens,
        "gen_ai.usage.cache_creation.input_tokens": r.cache_write_tokens,
        "gen_ai.response.finish_reasons": [r.stop_reason] if r.stop_reason else [],
        "lantern.tool_calls": len(r.tool_calls),
        "lantern.cost_usd": r.cost_usd,
        "lantern.latency_s": round(r.seconds, 3),
        "lantern.eval_s": round(r.eval_seconds, 3),
        "lantern.attempts": r.attempts,
        "lantern.unsupported": r.unsupported,
    }


def log(r: Reply) -> None:
    p = path()
    if p is None:
        return
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(record(r), default=str) + "\n")
    except OSError:
        pass  # a log that cannot be written must never stop a lesson


def read(p: Path | None = None) -> list[dict[str, Any]]:
    p = p or path()
    if not p or not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]

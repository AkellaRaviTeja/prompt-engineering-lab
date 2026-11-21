"""Recorded hosted runs: record once with a key, replay forever without one.

    make lesson N=08 TIER=hosted RECORD=1      # live, and saves every call to recordings/hosted/
    make lesson N=08 TIER=hosted REPLAY=1      # no key, no network: answers from the recording

A recording is one JSON line per call in `recordings/hosted/<chapter>.jsonl`, keyed by a hash of
everything that decides the answer (provider, model, messages, schema, tools, settings), so a
changed prompt misses the recording instead of silently reusing an old answer. The run's
`learn.record()` numbers are saved beside it as `<chapter>-results.json`, and that is what
`make challenge N=NN TIER=hosted` checks when no key is set.

Only synthetic material is ever recorded: the case files are fictional.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lantern.config import ROOT
from lantern.llm import Reply, ToolCall

DIR = ROOT / "recordings" / "hosted"
_SETTINGS = ("max_tokens", "think", "logprobs", "cache", "temperature", "seed")


def _chapter() -> str:
    from lantern.learn import chapter_of

    return chapter_of()


def path(chapter: str | None = None) -> Path:
    override = os.getenv("LANTERN_RECORDING")
    return Path(override) if override else DIR / f"{chapter or _chapter()}.jsonl"


def key(provider, messages, model, s, format, tools) -> str:
    blob = json.dumps(
        [provider, model, messages, format, tools, {k: s.get(k) for k in _SETTINGS}],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def save(provider, messages, model, s, format, tools, reply: Reply) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(reply)
    data.pop("raw", None)
    line = {"key": key(provider, messages, model, s, format, tools), "reply": data}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, default=str) + "\n")


def load(p: Path) -> dict[str, dict[str, Any]]:
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            out.setdefault(item["key"], item["reply"])
    return out


def replay(provider, messages, model, s, format, tools) -> Reply:
    p = path()
    k = key(provider, messages, model, s, format, tools)
    hit = load(p).get(k)
    if hit is None:
        raise SystemExit(
            f"No recorded hosted reply for this request in {p.relative_to(ROOT)} (key {k}). "
            "The prompt or settings changed since the recording, or this chapter has not been "
            "recorded yet: record it with a key, `make lesson N=NN TIER=hosted RECORD=1`."
        )
    hit = dict(hit)
    hit["tool_calls"] = [ToolCall(**c) for c in hit.get("tool_calls", [])]
    return Reply(**hit)


def save_results(chapter: str, payload: dict[str, Any]) -> Path:
    out = DIR / f"{chapter}-results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return out


def results(chapter: str) -> dict[str, Any] | None:
    try:
        return json.loads((DIR / f"{chapter}-results.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

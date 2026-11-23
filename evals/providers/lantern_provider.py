"""A promptfoo provider that calls LANTERN through `lantern.chat`, the path chapter 08 built.

With `schema` in its config the call is schema-constrained: Ollama turns the schema into a
grammar, a hosted provider uses its native structured output. The reply is JSON by construction,
so the extraction suite needs no fence-stripping transform. Every call is also logged with its
prompt version, model, tokens, cost and latency (`.progress/calls.jsonl`).

    providers:
      - id: file://providers/lantern_provider.py
        label: qwen3-1.7b
        config: {model: qwen3:1.7b, schema: file://schemas/invoice.json}

`tier: hosted` in the config (or LANTERN_TIER=hosted in the environment) sends the call to the
hosted provider instead of Ollama: promptfooconfig.hosted.yaml uses it for every prompt.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lantern import chat  # noqa: E402
from lantern.config import load_config  # noqa: E402


def _schema(value):
    if isinstance(value, str) and value.startswith("file://"):
        return json.loads((ROOT / "evals" / value[len("file://"):]).read_text(encoding="utf-8"))
    return value


def use_tier(name: str | None) -> None:
    """Point lantern at a tier for the calls that follow (config is cached, so clear it)."""
    if name and os.environ.get("LANTERN_TIER") != name:
        os.environ["LANTERN_TIER"] = name
        load_config.cache_clear()


def call_api(prompt: str, options: dict, context: dict) -> dict:
    cfg = options.get("config", {})
    use_tier(cfg.get("tier"))
    try:
        messages = json.loads(prompt)
    except ValueError:
        messages = prompt
    label = (context or {}).get("prompt", {}).get("label", "")
    r = chat(
        messages,
        model=cfg.get("model"),
        format=_schema(cfg.get("schema")),
        temperature=cfg.get("temperature", 0),
        seed=cfg.get("seed", 7),
        max_tokens=cfg.get("max_tokens", 300),
        think=cfg.get("think", False),
        prompt_version=f"{label}@{cfg.get('prompt_version', 'v1')}" if label else None,
    )
    return {
        "output": r.text,
        "tokenUsage": {"prompt": r.prompt_tokens, "completion": r.output_tokens,
                       "total": r.prompt_tokens + r.output_tokens,
                       "cached": r.cached_tokens},
        "cost": r.cost_usd or 0.0,
        "latencyMs": int(r.seconds * 1000),
        # Settings the hosted provider does not take (temperature, seed), reported, not dropped.
        "metadata": {"model": r.model, "unsupported": list(r.unsupported or [])},
    }

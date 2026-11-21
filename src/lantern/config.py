"""Load config.yaml and apply environment overrides."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if provider := os.getenv("LANTERN_PROVIDER"):
        cfg["provider"] = provider
    if tier := os.getenv("LANTERN_TIER") or os.getenv("TIER"):
        cfg["tier"] = tier
    if hosted := os.getenv("LANTERN_HOSTED_PROVIDER"):
        cfg["hosted"]["provider"] = hosted
    if model := os.getenv("LANTERN_MODEL"):
        cfg["models"]["default"] = model
    if host := os.getenv("OLLAMA_HOST"):
        cfg["ollama"]["host"] = host if host.startswith("http") else f"http://{host}"
    return cfg


def provider_of(cfg: dict[str, Any] | None = None) -> str:
    """The provider calls go to: Ollama on the local tier, the hosted provider on `hosted`.

    LANTERN_PROVIDER=anthropic (the older switch) still works and means the hosted tier.
    """
    cfg = cfg or load_config()
    if cfg.get("tier", "local") == "hosted":
        return cfg["hosted"]["provider"]
    if cfg.get("tier", "local") != "local":
        raise SystemExit(f"Unknown tier {cfg['tier']!r}. Use TIER=local or TIER=hosted.")
    return cfg["provider"]


def tier() -> str:
    return "local" if provider_of() == "ollama" else "hosted"


def model_name(alias_or_name: str | None) -> str:
    """Resolve 'small' / 'default' / 'large' to a model name; pass real names through.

    On the hosted tier the aliases resolve to the hosted provider's models, and a local model
    name a lesson asks for by name (qwen3:4b) resolves to the hosted model at the same alias.
    """
    cfg = load_config()
    local = cfg["models"]
    provider = provider_of(cfg)
    if provider == "ollama":
        return (
            local["default"] if alias_or_name is None else local.get(alias_or_name, alias_or_name)
        )
    hosted = cfg["hosted"][provider]["models"]
    if alias_or_name is None:
        return hosted["default"]
    if alias_or_name in hosted:
        return hosted[alias_or_name]
    for alias, name in local.items():
        if name == alias_or_name:
            return hosted.get(alias, hosted["default"])
    return alias_or_name


def price_of(model: str) -> dict[str, float] | None:
    """USD per million tokens for a model, or None when config.yaml has no checked price."""
    p = load_config().get("prices", {}).get(model)
    if not p or p.get("input") is None:
        return None
    return p

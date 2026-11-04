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
    if model := os.getenv("LANTERN_MODEL"):
        cfg["models"]["default"] = model
    if host := os.getenv("OLLAMA_HOST"):
        cfg["ollama"]["host"] = host if host.startswith("http") else f"http://{host}"
    return cfg


def model_name(alias_or_name: str | None) -> str:
    """Resolve 'small' / 'default' / 'large' to a model name; pass real names through."""
    models = load_config()["models"]
    if alias_or_name is None:
        return models["default"]
    return models.get(alias_or_name, alias_or_name)

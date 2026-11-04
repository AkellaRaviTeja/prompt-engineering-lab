"""Check that LANTERN is ready: Ollama reachable, models pulled, config sane."""

from __future__ import annotations

import sys

import httpx

from lantern.config import load_config


def main() -> int:
    cfg = load_config()
    checks: list[tuple[str, bool, str]] = []
    host = cfg["ollama"]["host"]
    try:
        version = httpx.get(f"{host}/api/version", timeout=5).json()["version"]
        checks.append(("Ollama reachable", True, f"{host} (version {version})"))
        tags = httpx.get(f"{host}/api/tags", timeout=5).json()["models"]
        pulled = {m["name"] for m in tags}
    except httpx.HTTPError as e:
        checks.append(("Ollama reachable", False, f"{host}: {e}. Run `make up`."))
        pulled = set()
    for alias, name in cfg["models"].items():
        checks.append((f"model {alias}", name in pulled, name if name in pulled
                       else f"{name} missing. Run `make models`."))
    checks.append(("provider", cfg["provider"] in {"ollama", "anthropic", "openai", "gemini"},
                   cfg["provider"]))
    for label, ok, detail in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {label:<18} {detail}")
    failed = sum(not ok for _, ok, _ in checks)
    print(f"doctor: {len(checks)} checks, {failed} failed")
    return 1 if failed or not checks else 0


if __name__ == "__main__":
    sys.exit(main())

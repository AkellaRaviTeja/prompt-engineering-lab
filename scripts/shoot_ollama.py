"""Terminal screenshots of the Ollama tool itself: list, ps, show, and a raw API call.

Run with `uv run python scripts/shoot_ollama.py`; writes docs/screenshots/00-ollama-*.svg.
"""

from __future__ import annotations

import json
import shlex
import subprocess

import httpx
from rich.console import Console
from rich.syntax import Syntax

from lantern.config import ROOT, load_config

OUT = ROOT / "docs" / "screenshots"


def ollama_cmd() -> list[str]:
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                           capture_output=True, text=True).stdout.split()
    return ["docker", "exec", "pel-ollama", "ollama"] if "pel-ollama" in names else ["ollama"]


def shot(name: str, title: str, commands: list[str]) -> None:
    console = Console(record=True, width=100)
    for cmd in commands:
        console.print(f"[bold green]$[/bold green] {cmd}")
        args = ollama_cmd() + shlex.split(cmd)[1:]
        out = subprocess.run(args, capture_output=True, text=True).stdout.rstrip()
        console.print(out, highlight=False, markup=False)
        console.print()
    console.save_svg(str(OUT / f"{name}.svg"), title=title)


def api_shot() -> None:
    host = load_config()["ollama"]["host"]
    body = {"model": load_config()["models"]["small"], "stream": False, "think": False,
            "messages": [{"role": "system", "content": "Answer in one short sentence."},
                         {"role": "user", "content": "What is a container terminal?"}],
            "options": {"temperature": 0, "seed": 7, "num_predict": 60}}
    data = httpx.post(f"{host}/api/chat", json=body, timeout=300).json()
    keep = {k: data[k] for k in ("model", "message", "done_reason", "prompt_eval_count",
                                  "eval_count", "eval_duration") if k in data}
    console = Console(record=True, width=100)
    console.print("[bold green]$[/bold green] curl -s localhost:11434/api/chat -d @request.json")
    console.print("[dim]request.json[/dim]")
    console.print(Syntax(json.dumps(body, indent=2), "json", theme="monokai", word_wrap=True))
    console.print("[dim]response (abridged)[/dim]")
    console.print(Syntax(json.dumps(keep, indent=2), "json", theme="monokai", word_wrap=True))
    console.save_svg(str(OUT / "00-ollama-api.svg"), title="Ollama HTTP API")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shot("00-ollama-cli", "Ollama CLI", ["ollama --version", "ollama list", "ollama ps"])
    shot("00-ollama-show", "ollama show", ["ollama show qwen3:1.7b"])
    api_shot()
    print("shoot_ollama: wrote 3 screenshots")


if __name__ == "__main__":
    main()

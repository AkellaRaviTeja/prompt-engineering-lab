"""Fail if any Markdown, Python, YAML or HTML file contains an em dash or en dash."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = {chr(0x2014): "em dash", chr(0x2013): "en dash"}
SKIP = {".venv", "node_modules", ".git", "output", "screenshots"}


def main() -> int:
    files = [p for ext in ("*.md", "*.py", "*.yaml", "*.yml", "*.html", "*.d2", "*.txt", "*.csv",
                           "*.jsonl")
             for p in ROOT.rglob(ext) if not SKIP & set(p.relative_to(ROOT).parts)]
    problems = []
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ch, name in BANNED.items():
                if ch in line:
                    problems.append(f"{path.relative_to(ROOT)}:{n}: {name}")
    print("\n".join(problems))
    print(f"prose: checked {len(files)} files, {len(problems)} problems")
    return 1 if problems or not files else 0


if __name__ == "__main__":
    sys.exit(main())

"""Every lesson folder must have a README with the required sections and a run.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "## The scene",
    "## The concept",
    "## How it works",
    "## The nuances",
    "## Run it",
    "## What you should see",
    "## Try this",
    "## What the evidence now shows",
]


def main() -> int:
    lessons = sorted(p for p in (ROOT / "lessons").glob("[0-9][0-9]-*") if p.is_dir())
    problems = []
    for lesson in lessons:
        readme = lesson / "README.md"
        if not (lesson / "run.py").exists():
            problems.append(f"{lesson.name}: missing run.py")
        if not readme.exists():
            problems.append(f"{lesson.name}: missing README.md")
            continue
        text = readme.read_text(encoding="utf-8")
        positions = []
        for heading in REQUIRED:
            if heading not in text:
                problems.append(f"{lesson.name}: missing section '{heading}'")
            else:
                positions.append(text.index(heading))
        if positions != sorted(positions):
            problems.append(f"{lesson.name}: sections out of order")
        if "```mermaid" not in text and not re.search(r"!\[[^\]]*\]\([^)]*diagrams/", text):
            problems.append(f"{lesson.name}: no diagram (mermaid block or docs/diagrams image)")
        for link in re.findall(r"\]\(([^)#]+)\)", text):
            if not link.startswith("http") and not (lesson / link).resolve().exists():
                problems.append(f"{lesson.name}: broken link {link}")
    print("\n".join(problems))
    print(f"structure: checked {len(lessons)} lessons, {len(problems)} problems")
    return 1 if problems or not lessons else 0


if __name__ == "__main__":
    sys.exit(main())

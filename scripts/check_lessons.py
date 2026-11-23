"""The structure gate: every chapter is complete, and so is the capstone.

Every lesson folder must have a run.py and a README with the required sections, in order, a scene
under 200 words, a diagram and no broken links. A finished lesson also has:

- a practice/ folder: practice.yaml (chapter check, exercise and hints, challenges),
  exercise.py (the stub), solution.py and test_exercise.py;
- a section "On a hosted model" with the hosted run's numbers, or "not run" where there are none.

At least a third of the exercises are components (`exercise.kind: component` in practice.yaml):
the learner writes a whole loop, gate or pipeline step, and run.py uses it in place of the lesson's
own with `--mine` (it must call `learn.mine()`).

The capstone (capstone/) must have its brief, its offline tests and its solution.

A README containing `<!-- status: draft -->` is a draft: it must still have every section in
order and a scene under 200 words, but it is excused the practice folder, the diagram and the
screenshot checks. With `--release`, any draft is a failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DRAFT = "<!-- status: draft -->"
REQUIRED = [
    "## The scene",
    "## The concept",
    "## How it works",
    "## The nuances",
    "## Run it",
    "## What you should see",
    "## On a hosted model",
    "## Try this",
    "## Master it",
    "## What the evidence now shows",
]
DRAFT_EXCUSED = {"## Master it", "## On a hosted model"}
PRACTICE = ("practice.yaml", "exercise.py", "solution.py", "test_exercise.py")
SCENE_LIMIT = 200
COMPONENT_SHARE = 1 / 3
# A line that is only a capitalised token (SEE, HOSTED) or an @@T11@@ marker: a section left
# for numbers from a run that has not been done; also an inline NUANCE3 or TODO marker.
PLACEHOLDER = re.compile(r"(?m)^(?:@@\w+@@|[A-Z][A-Z_]{2,})\s*$|@@\w+@@|\bNUANCE\d+\b|\bTODO\b")


def scene_words(text: str) -> int:
    start = text.index("## The scene") + len("## The scene")
    end = text.index("## The concept", start)
    return len(text[start:end].split())


def section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading)
    nxt = text.find("\n## ", start)
    return text[start : nxt if nxt != -1 else len(text)]


def check_practice(lesson: Path, problems: list[str]) -> str | None:
    """Problems with a finished lesson's practice/; returns the exercise kind."""
    folder = lesson / "practice"
    missing = [f for f in PRACTICE if not (folder / f).exists()]
    for f in missing:
        problems.append(f"{lesson.name}: missing practice/{f}")
    if "practice.yaml" in missing:
        return None
    p = yaml.safe_load((folder / "practice.yaml").read_text(encoding="utf-8")) or {}
    quiz, challenges = p.get("quiz") or [], p.get("challenges") or []
    if not 5 <= len(quiz) <= 8:
        problems.append(f"{lesson.name}: chapter check has {len(quiz)} questions (5 to 8)")
    if not 2 <= len(challenges) <= 4:
        problems.append(f"{lesson.name}: {len(challenges)} challenges (2 to 4)")
    ex = p.get("exercise") or {}
    if len(ex.get("hints") or []) < 3:
        problems.append(f"{lesson.name}: the exercise needs three hints")
    kind = ex.get("kind", "function")
    if kind not in ("function", "component"):
        problems.append(f"{lesson.name}: exercise.kind must be function or component")
    if kind == "component" and "learn.mine()" not in (lesson / "run.py").read_text("utf-8"):
        problems.append(f"{lesson.name}: a component exercise must be usable with --mine")
    return kind


def check_capstone(problems: list[str]) -> None:
    cap = ROOT / "capstone"
    if not (cap / "README.md").exists():
        problems.append("capstone: missing README.md (the brief)")
    if not list((cap / "tests").glob("test_*.py")):
        problems.append("capstone: no tests in capstone/tests/")
    readme = cap / "README.md"
    if readme.exists():
        for ph in (m.group(0) for m in PLACEHOLDER.finditer(readme.read_text(encoding="utf-8"))):
            problems.append(f"capstone: placeholder {ph.strip()!r} still in the README")
    if not list((cap / "solution").glob("*.py")):
        problems.append("capstone: no solution in capstone/solution/")


def main() -> int:
    release = "--release" in sys.argv
    lessons = sorted(p for p in (ROOT / "lessons").glob("[0-9][0-9]-*") if p.is_dir())
    problems: list[str] = []
    drafts: list[str] = []
    kinds: list[str] = []
    for lesson in lessons:
        readme = lesson / "README.md"
        if not (lesson / "run.py").exists():
            problems.append(f"{lesson.name}: missing run.py")
        if not readme.exists():
            problems.append(f"{lesson.name}: missing README.md")
            continue
        text = readme.read_text(encoding="utf-8")
        is_draft = DRAFT in text
        if is_draft:
            drafts.append(lesson.name)
        else:
            kind = check_practice(lesson, problems)
            if kind:
                kinds.append(kind)
        positions = []
        for heading in REQUIRED:
            if is_draft and heading in DRAFT_EXCUSED and heading not in text:
                continue
            if heading not in text:
                problems.append(f"{lesson.name}: missing section '{heading}'")
            else:
                positions.append(text.index(heading))
        if positions != sorted(positions):
            problems.append(f"{lesson.name}: sections out of order")
        if "## On a hosted model" in text:
            hosted = section(text, "## On a hosted model")
            if "not run" not in hosted and not re.search(r"\|\s*[\d.,]+\s*\|", hosted):
                problems.append(f"{lesson.name}: hosted section has no numbers and no 'not run'")
        if "## The scene" in text and "## The concept" in text:
            words = scene_words(text)
            if words > SCENE_LIMIT:
                problems.append(f"{lesson.name}: scene is {words} words (limit {SCENE_LIMIT})")
        for ph in (m.group(0) for m in PLACEHOLDER.finditer(text)):
            problems.append(f"{lesson.name}: placeholder {ph.strip()!r} still in the README")
        has_diagram = "```mermaid" in text or re.search(r"!\[[^\]]*\]\([^)]*diagrams/", text)
        if not is_draft and not has_diagram:
            problems.append(f"{lesson.name}: no diagram (mermaid block or docs/diagrams image)")
        for link in re.findall(r"\]\(([^)#]+)\)", text):
            if not link.startswith("http") and not (lesson / link).resolve().exists():
                if not (is_draft and "screenshots/" in link):
                    problems.append(f"{lesson.name}: broken link {link}")
    components = kinds.count("component")
    if kinds and components < COMPONENT_SHARE * len(kinds):
        problems.append(
            f"practice: {components} of {len(kinds)} exercises are components "
            f"(at least a third must be)"
        )
    check_capstone(problems)
    if release:
        problems += [f"{name}: still a draft" for name in drafts]
    print("\n".join(problems))
    print(
        f"structure: checked {len(lessons)} lessons, {len(drafts)} drafts, "
        f"{components} of {len(kinds)} exercises are components, capstone checked, "
        f"{len(problems)} problems"
    )
    return 1 if problems or not lessons else 0


if __name__ == "__main__":
    sys.exit(main())

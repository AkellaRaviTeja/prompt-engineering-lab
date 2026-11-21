"""lantern.learn: the learner's side of a lesson. Predict, then see; and a record of each run.

A lesson asks for a prediction before a step, runs the step, then reveals what really happened
and why. The answer is always computed from this run, never written in advance: a model run can
go differently, and the reveal says what *this* run did.

    p = learn.predict("How many turns before LANTERN answers?", ["1 to 3", "4 to 6", "7 or more"])
    ...                                      # run the step
    learn.reveal(p, answer=learn.bucket(turns, [3, 6]), why="Every turn resends ...")

    p = learn.predict_number("How many prompt tokens will the last turn carry?")
    learn.reveal(p, actual=last_tokens, tolerance=0.3, why="...")

    learn.record(turns=turns, flows_in_report=4)   # read by `make challenge N=NN`

Predictions are asked only when a person is there to answer: a terminal or a notebook. With
`--shot`, `--no-predict`, LANTERN_PREDICT=0 or no terminal (CI, `make lessons`), predict and
reveal print nothing, so screenshots and logs show the lesson exactly as before.

Progress (predictions, chapter checks, exercises, challenges) is kept in `.progress/`, which git
ignores. `make progress` shows it.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.panel import Panel

from lantern.config import ROOT, load_config
from lantern.ui import SHOT, console

PROGRESS = ROOT / ".progress"
LETTERS = "abcdefghij"

__all__ = [
    "Prediction",
    "ask_letter",
    "bucket",
    "chapter_of",
    "interactive",
    "load_progress",
    "mine",
    "predict",
    "predict_number",
    "record",
    "results",
    "reveal",
    "save_progress",
]


def interactive() -> bool:
    """True when a person can answer: a terminal or a notebook, and predictions not turned off."""
    if SHOT or "--no-predict" in sys.argv or os.getenv("LANTERN_PREDICT", "1") == "0":
        return False
    return "ipykernel" in sys.modules or sys.stdin.isatty()


def chapter_of(path: str | Path | None = None) -> str:
    """The two-digit chapter number of the running lesson (from its folder name), or '00'."""
    if os.getenv("LANTERN_CHAPTER"):
        return os.environ["LANTERN_CHAPTER"]
    p = Path(path or sys.argv[0]).resolve()
    for part in (p.parent.name, p.parent.parent.name, p.name):
        if part[:2].isdigit() and part[2:3] == "-":
            return part[:2]
    return "00"


# ---- progress file -----------------------------------------------------------------------------


def _progress_file() -> Path:
    return PROGRESS / "progress.json"


def load_progress() -> dict[str, Any]:
    try:
        return json.loads(_progress_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_progress(data: dict[str, Any]) -> None:
    _progress_file().parent.mkdir(parents=True, exist_ok=True)
    _progress_file().write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _chapter_progress(data: dict[str, Any], chapter: str) -> dict[str, Any]:
    return data.setdefault(chapter, {})


def changed_since_head(chapter: str) -> bool | None:
    """True if the lesson (outside practice/), case/, src/ or config.yaml differs from git HEAD.

    A challenge that asks for a change only counts on a run made with one. None when git cannot
    tell (no git, not a checkout), and then challenges are not held back.
    """
    import subprocess

    lesson = next(iter(sorted((ROOT / "lessons").glob(f"{chapter}-*"))), None)
    if lesson is None:
        return None
    name = lesson.relative_to(ROOT).as_posix()
    paths = [
        name,
        "case",
        "src",
        "config.yaml",
        f":(exclude){name}/practice",
        f":(exclude){name}/lesson.ipynb",
    ]
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", *paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(r.stdout.strip()) if r.returncode == 0 else None


def record(**metrics: Any) -> dict[str, Any]:
    """Save this run's measurements for `make challenge`. Values must be JSON-serialisable."""
    from lantern.config import provider_of

    chapter = chapter_of()
    provider = provider_of(load_config())
    # Hosted results never replace the local run the challenges check: they are kept as
    # NN-hosted, and `make challenge N=NN TIER=hosted` checks those.
    name = chapter if provider == "ollama" else f"{chapter}-hosted"
    out = PROGRESS / "results" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chapter": chapter,
        "at": datetime.now().isoformat(timespec="seconds"),
        "argv": sys.argv[1:],
        "provider": provider,
        "changed": changed_since_head(chapter),
        "metrics": metrics,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    if provider != "ollama" and os.getenv("LANTERN_RECORD"):
        from lantern import recording

        recording.save_results(chapter, payload)
    return payload


def mine() -> Any | None:
    """With `--mine`, the learner's practice/exercise.py for this lesson, loaded; else None.

    `make lesson N=05 ARGS=--mine` runs the live lesson on your own code instead of the lesson's.
    """
    if "--mine" not in sys.argv:
        return None
    import importlib.util

    path = Path(sys.argv[0]).resolve().parent / "practice" / "exercise.py"
    spec = importlib.util.spec_from_file_location(f"mine_{chapter_of()}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    console.print(
        Panel(
            f"Running on your code: {path.relative_to(ROOT)}",
            title="[bold]--mine[/bold]",
            border_style="yellow",
        )
    )
    return module


def results(chapter: str) -> dict[str, Any] | None:
    """The measurements from the latest run of a chapter, or None if it has not been run.

    `chapter` may be "08" (the local run) or "08-hosted". With no hosted run of your own, the
    committed recorded hosted run is used, so a learner without a key can still check it.
    """
    try:
        return json.loads((PROGRESS / "results" / f"{chapter}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if chapter.endswith("-hosted"):
            from lantern import recording

            return recording.results(chapter[:2])
        return None


# ---- predictions -------------------------------------------------------------------------------


@dataclass
class Prediction:
    question: str
    options: list[str] = field(default_factory=list)  # empty for a number
    guess: Any = None  # an option index, a number, or None when skipped
    asked: bool = False
    unit: str = ""

    @property
    def is_number(self) -> bool:
        return not self.options

    @property
    def key(self) -> str:
        """The progress key: the question with its run-specific numbers taken out, so a rerun
        of the same question replaces its earlier result instead of adding a new one."""
        return re.sub(r"\d[\d,.]*", "#", self.question)


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def ask_letter(n_options: int, label: str, *, allow_skip: bool, ask=_ask) -> int | None:
    """Prompt until one valid letter is typed; return its index. Enter returns None if allowed."""
    valid = LETTERS[:n_options]
    hint = f"{valid[0]} to {valid[-1]}" + (", Enter skips" if allow_skip else "")
    while True:
        a = ask(f"{label} ({hint}): ").lower()
        if not a and allow_skip:
            return None
        if len(a) == 1 and a in valid:
            return LETTERS.index(a)
        console.print("[dim]One letter, please.[/dim]")


def predict(question: str, options: list[str]) -> Prediction:
    """Ask a multiple-choice prediction before a step runs. Enter skips it."""
    p = Prediction(question, list(options))
    if not interactive():
        return p
    body = "\n".join(f"  [bold]{LETTERS[i]}[/bold]) {o}" for i, o in enumerate(options))
    console.print()
    console.print(
        Panel(f"{question}\n\n{body}", title="[bold]Predict first[/bold]", border_style="yellow")
    )
    p.guess = ask_letter(len(options), "Your prediction", allow_skip=True)
    p.asked = True
    return p


def predict_number(question: str, *, unit: str = "") -> Prediction:
    """Ask for a number before a step runs. Enter skips it."""
    p = Prediction(question, unit=unit)
    if not interactive():
        return p
    console.print()
    console.print(Panel(question, title="[bold]Predict first[/bold]", border_style="yellow"))
    while True:
        a = _ask("Your estimate (a number, Enter skips): ").replace(",", "")
        if not a:
            break
        try:
            p.guess = float(a)
            break
        except ValueError:
            console.print("[dim]A number, please.[/dim]")
    p.asked = True
    return p


def bucket(value: float, edges: list[float]) -> int:
    """Which option a value falls in, for options like '1 to 3', '4 to 6', '7 or more'.

    `edges` are the upper bounds of every option but the last: bucket(5, [3, 6]) == 1.
    """
    for i, edge in enumerate(edges):
        if value <= edge:
            return i
    return len(edges)


def reveal(
    p: Prediction,
    *,
    answer: int | None = None,
    actual: float | None = None,
    tolerance: float = 0.25,
    why: str = "",
) -> bool | None:
    """Show what this run did against the prediction. Returns True/False, or None if skipped.

    For a choice, `answer` is the index of the option this run bore out. For a number, `actual`
    is the measured value and a guess within `tolerance` (a fraction of it) counts as right.
    """
    if not p.asked:
        return None
    if p.is_number:
        if actual is None:
            raise ValueError("reveal() of a number needs actual=")
        shown = f"{actual:,.0f}" if float(actual).is_integer() else f"{actual:,.2f}"
        truth = f"{shown}{' ' + p.unit if p.unit else ''}"
        right = None if p.guess is None else abs(p.guess - actual) <= abs(actual) * tolerance
        yours = "skipped" if p.guess is None else f"{p.guess:,.0f}"
        margin = f" (within {tolerance:.0%} counts)"
    else:
        if answer is None:
            raise ValueError("reveal() of a choice needs answer=")
        truth = f"{LETTERS[answer]}) {p.options[answer]}"
        right = None if p.guess is None else p.guess == answer
        yours = "skipped" if p.guess is None else f"{LETTERS[p.guess]}) {p.options[p.guess]}"
        margin = ""
    verdict = {True: "[green]Right.[/green]", False: "[red]Not this time.[/red]", None: ""}[right]
    console.print(
        Panel(
            f"{verdict} You said: {yours}. This run: [bold]{truth}[/bold]{margin}."
            + (f"\n\n{why}" if why else ""),
            title="[bold]What happened[/bold]",
            border_style="green" if right else ("red" if right is False else "dim"),
        )
    )
    if right is not None:
        data = load_progress()
        preds = _chapter_progress(data, chapter_of()).setdefault("predictions", {})
        preds[p.key] = right
        save_progress(data)
    return right

"""The practice side of every chapter: chapter checks, exercises, hints, challenges, progress.

    make quiz N=05            the chapter check: questions, with why after each answer
    make exercise N=05        grade your lessons/05-*/practice/exercise.py (offline, no model)
    make hint N=05            the next hint for the exercise
    make solution N=05        the reference solution, once you have tried
    make challenge N=05       the break-it challenges, checked against your latest run
    make progress             every chapter: predictions, check, exercise, challenges

Everything a chapter offers is in its lessons/NN-*/practice/practice.yaml.
"""

from __future__ import annotations

import operator
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lantern.learn import LETTERS, ask_letter, load_progress, results, save_progress  # noqa: E402

console = Console()
OPS = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
}
METRIC_NAME = re.compile(r"[a-z_][a-z0-9_]*")
CONDITION = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(<=|>=|==|!=|<|>)\s*(.+?)\s*$")


# ---- loading -----------------------------------------------------------------------------------


def lesson_dir(n: str) -> Path:
    n = n.zfill(2)
    found = sorted((ROOT / "lessons").glob(f"{n}-*"))
    if not found:
        raise SystemExit(f"No lesson {n}. Lessons are 01 to 23.")
    return found[0]


def practice(n: str) -> dict[str, Any]:
    f = lesson_dir(n) / "practice" / "practice.yaml"
    if not f.exists():
        raise SystemExit(f"Chapter {n} has no practice yet ({f.relative_to(ROOT)}).")
    return yaml.safe_load(f.read_text(encoding="utf-8"))


def chapter_progress(data: dict[str, Any], n: str) -> dict[str, Any]:
    return data.setdefault(n.zfill(2), {})


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        raise SystemExit("\nThis needs a terminal to answer in.") from None


# ---- the chapter check -------------------------------------------------------------------------


def quiz(n: str) -> int:
    p = practice(n)
    qs = p["quiz"]
    console.rule(f"[bold]Chapter {n} check: {p['title']}[/bold]", style="yellow")
    if p.get("objectives"):
        console.print("[bold]After this chapter you can:[/bold]")
        for o in p["objectives"]:
            console.print(f"  - {o}")
    score = 0
    for i, q in enumerate(qs, 1):
        q = shuffled(q)
        opts = "\n".join(f"  [bold]{LETTERS[j]}[/bold]) {o}" for j, o in enumerate(q["options"]))
        console.print()
        console.print(Panel(f"{q['q']}\n\n{opts}", title=f"Question {i} of {len(qs)}"))
        a = LETTERS[ask_letter(len(q["options"]), "Your answer", allow_skip=False, ask=ask)]
        right = a == q["answer"]
        score += right
        truth = f"{q['answer']}) {q['options'][LETTERS.index(q['answer'])]}"
        console.print(
            Panel(
                ("[green]Right.[/green] " if right else f"[red]No.[/red] The answer is {truth}. ")
                + q["why"].strip(),
                border_style="green" if right else "red",
            )
        )
    data = load_progress()
    cp = chapter_progress(data, n)
    cp["quiz"] = {"best": max(score, cp.get("quiz", {}).get("best", 0)), "of": len(qs)}
    save_progress(data)
    console.print()
    mastered = score == len(qs)
    console.print(
        f"[bold]{score} of {len(qs)}.[/bold] "
        + (
            "Every concept in this chapter is yours."
            if mastered
            else "Reread the nuances for the ones you missed, then run `make quiz N="
            + n
            + "` again."
        )
    )
    return 0


ORDERED = re.compile(r"^(\d|none|all|every|fewer|more|the same|both|neither|only)\b", re.I)


def shuffled(q: dict[str, Any]) -> dict[str, Any]:
    """The question with its options in a fixed shuffled order, so the right letter varies.

    The order is seeded by the question text: the same for everyone, every time. Options that
    form a scale (numbers, none/some/all, fewer/same/more) keep their order, as does any question
    with `keep_order: true`.
    """
    opts = q["options"]
    if q.get("keep_order") or any(ORDERED.match(o.strip()) for o in opts):
        return q
    order = list(range(len(opts)))
    random.Random(q["q"]).shuffle(order)
    right = LETTERS.index(q["answer"])
    return {**q, "options": [opts[j] for j in order], "answer": LETTERS[order.index(right)]}


# ---- the exercise ------------------------------------------------------------------------------


def exercise(n: str) -> int:
    p = practice(n)
    ex = p["exercise"]
    folder = lesson_dir(n) / "practice"
    console.rule(f"[bold]Chapter {n} exercise: {ex['title']}[/bold]", style="cyan")
    console.print(Markdown(ex["task"].strip()))
    console.print(f"\n[dim]Your file: {(folder / 'exercise.py').relative_to(ROOT)}[/dim]\n")
    env = {**os.environ, "LANTERN_EXERCISE": "learner"}
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(folder),
            "-q",
            "--no-header",
            "-rA",
            "--tb=line",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    out = r.stdout + r.stderr
    outcome = {
        name: status
        for status, name in re.findall(r"^(PASSED|FAILED|ERROR) \S+?::(\w+)", out, re.M)
    }
    docs = _test_docs(folder)
    table = Table(title="What the tests check")
    table.add_column("")
    table.add_column("behaviour")
    for name, doc in docs.items():
        mark = {"PASSED": "[green]pass[/green]", "FAILED": "[red]fail[/red]"}.get(
            outcome.get(name, ""), "[red]error[/red]"
        )
        table.add_row(mark, doc or name)
    console.print(table)
    passed = sum(s == "PASSED" for s in outcome.values())
    to_go = len(docs) - passed
    if "NotImplementedError" in out and passed == 0:
        console.print(
            "[yellow]The stubs still raise NotImplementedError. Start with the first TODO.[/yellow]"
        )
    elif to_go:
        for line in out.splitlines():
            if re.search(r"\.py:\d+: ", line):
                console.print(f"[dim]{line.strip()}[/dim]")
    data = load_progress()
    cp = chapter_progress(data, n)
    cp.setdefault("exercise", {})["attempts"] = cp.get("exercise", {}).get("attempts", 0) + 1
    if r.returncode == 0:
        cp["exercise"]["passed"] = True
        save_progress(data)
        console.print(f"\n[bold green]All {passed} tests pass.[/bold green] " + ex.get("after", ""))
        return 0
    save_progress(data)
    console.print(f"\n[bold]{passed} passed, {to_go} to go.[/bold] Stuck? `make hint N={n}`.")
    return 1


def _test_docs(folder: Path) -> dict[str, str]:
    """Each test's name and the first line of its docstring, in file order."""
    src = (folder / "test_exercise.py").read_text(encoding="utf-8")
    pattern = r'^def (test_\w+)\([^)]*\):\n\s+(?:"""(.+?)(?:"""|\n))?'
    return {m.group(1): (m.group(2) or "").strip() for m in re.finditer(pattern, src, re.M)}


def hint(n: str) -> int:
    hints = practice(n)["exercise"].get("hints", [])
    data = load_progress()
    cp = chapter_progress(data, n)
    shown = cp.setdefault("exercise", {}).get("hints", 0)
    if not hints:
        console.print("No hints for this exercise.")
        return 0
    i = min(shown, len(hints) - 1)
    console.print(Panel(Markdown(hints[i].strip()), title=f"Hint {i + 1} of {len(hints)}"))
    cp["exercise"]["hints"] = min(shown + 1, len(hints))
    save_progress(data)
    if i + 1 == len(hints):
        console.print(f"[dim]That was the last hint. `make solution N={n}` shows the answer.[/dim]")
    return 0


def solution(n: str) -> int:
    folder = lesson_dir(n) / "practice"
    cp = chapter_progress(load_progress(), n)
    if not cp.get("exercise", {}).get("attempts") and "--force" not in sys.argv:
        console.print(
            f"Try it first: `make exercise N={n}`. The solution teaches more once you have "
            "met the problem. (`make solution N=" + n + " ARGS=--force` shows it anyway.)"
        )
        return 1
    code = (folder / "solution.py").read_text(encoding="utf-8")
    console.print(Syntax(code, "python", line_numbers=True))
    return 0


# ---- challenges --------------------------------------------------------------------------------


def evaluate(target: str, metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check a target like 'turns <= 6 and flows_in_report == 4' against a run's metrics.

    The right-hand side is a value, or the name of another metric ('hand_turns <= native_turns').
    """
    ok, lines = True, []
    for part in re.split(r"\s+and\s+", target.strip()):
        m = CONDITION.match(part)
        if not m:
            raise ValueError(f"cannot read target condition {part!r}")
        name, op, raw = m.groups()
        if METRIC_NAME.fullmatch(raw) and raw not in ("true", "false", "null"):
            want: Any = metrics.get(raw)  # another metric of the same run
        else:
            want = yaml.safe_load(raw)
        have = metrics.get(name)
        good = have is not None and want is not None and OPS[op](have, want)
        ok &= good
        lines.append(
            f"{'[green]met[/green]' if good else '[red]not yet[/red]'}  {name} {op} "
            f"{want!r} (your run: {have!r})"
        )
    return ok, lines


def challenge(n: str) -> int:
    p = practice(n)
    hosted = (os.getenv("LANTERN_TIER") or os.getenv("TIER")) == "hosted"
    res = results(n.zfill(2) + ("-hosted" if hosted else ""))
    metrics = (res or {}).get("metrics", {})
    data = load_progress()
    done = chapter_progress(data, n).setdefault("challenges", {})
    console.rule(f"[bold]Chapter {n} challenges[/bold]", style="magenta")
    if res:
        console.print(
            f"[dim]Checked against your latest run: {res['at']} {' '.join(res['argv'])}[/dim]"
        )
    else:
        console.print(f"[yellow]No run recorded yet. Run `make lesson N={n}` first.[/yellow]")
    wanted = os.getenv("ID")
    for c in p["challenges"]:
        if wanted and c["id"] != wanted:
            continue
        met, lines = evaluate(c["target"], metrics) if res else (False, [])
        # A challenge with something to undo asks for a change: an unchanged run does not count,
        # however it turned out. (--mine challenges are checked by their `mine` metric.)
        if met and c.get("reset") and res.get("changed") is False:
            met = False
            lines.append(
                "[yellow]not counted[/yellow]  that run used the lesson as it is in git: "
                "make the change, then run the lesson again"
            )
        if met:
            done[c["id"]] = True
        status = "[green]done[/green]" if done.get(c["id"]) else "open"
        body = (
            f"[bold]Goal:[/bold] {c['goal'].strip()}\n\n[bold]Change:[/bold] {c['change'].strip()}"
            f"\n\n[bold]Target:[/bold] {c['target']}\n" + "\n".join(lines)
        )
        if c.get("reset"):
            body += f"\n\n[dim]Undo afterwards: {c['reset']}[/dim]"
        console.print(Panel(body, title=f"{c['title']}  ({c['id']}, {status})"))
    save_progress(data)
    return 0


# ---- progress ----------------------------------------------------------------------------------


def progress() -> int:
    data = load_progress()
    table = Table(title="Your progress through Case File 01")
    for col in ("chapter", "predictions right", "check", "exercise", "challenges"):
        table.add_column(col)
    totals = {"mastered": 0, "chapters": 0}
    for d in sorted((ROOT / "lessons").glob("[0-9][0-9]-*")):
        n = d.name[:2]
        f = d / "practice" / "practice.yaml"
        if not f.exists():
            table.add_row(d.name, "", "", "", "[dim]not yet written[/dim]")
            continue
        p = yaml.safe_load(f.read_text(encoding="utf-8"))
        cp = data.get(n, {})
        preds = cp.get("predictions", {})
        q = cp.get("quiz")
        ex = cp.get("exercise", {})
        ch = cp.get("challenges", {})
        quiz_ok = q and q["best"] == q["of"]
        mastered = quiz_ok and ex.get("passed") and ch
        totals["chapters"] += 1
        totals["mastered"] += bool(mastered)
        table.add_row(
            ("[green]" if mastered else "") + d.name,
            f"{sum(preds.values())} of {len(preds)}" if preds else "",
            f"{q['best']} of {q['of']}" if q else "",
            "passed"
            if ex.get("passed")
            else (f"{ex['attempts']} tries" if ex.get("attempts") else ""),
            f"{sum(1 for v in ch.values() if v)} of {len(p['challenges'])}",
        )
    console.print(table)
    console.print(
        f"Mastered (full check, exercise passed, at least one challenge): "
        f"{totals['mastered']} of {totals['chapters']} chapters."
    )
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, n = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    if cmd == "progress":
        return progress()
    if not n:
        raise SystemExit(f"usage: make {cmd} N=05")
    return {
        "quiz": quiz,
        "exercise": exercise,
        "hint": hint,
        "solution": solution,
        "challenge": challenge,
    }[cmd](n)


if __name__ == "__main__":
    sys.exit(main())

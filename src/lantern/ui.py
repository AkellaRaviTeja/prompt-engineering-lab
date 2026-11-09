"""Terminal output for lessons, with an optional screenshot of the whole run.

Run any lesson with `--shot` and the terminal output is saved as an SVG
under docs/screenshots/, which is how the screenshots in the READMEs are made.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from lantern.config import ROOT, load_config

SHOT = "--shot" in sys.argv
console = Console(record=SHOT, width=110 if SHOT else None)

__all__ = ["Table", "chapter", "console", "evidence", "finding", "note", "reply", "save_shot",
           "step", "your_turn"]


def _prose(text: str) -> str:
    """Join hard-wrapped lines into paragraphs so panels wrap to the terminal width."""
    paras = re.split(r"\n\s*\n", text.strip())
    return "\n\n".join(" ".join(line.strip() for line in p.splitlines()) for p in paras)


def lesson_dir(number: str) -> Path:
    """The folder of lesson `number`, e.g. lessons/01-prompt-engineering."""
    matches = sorted((ROOT / "lessons").glob(f"{number}-*"))
    if not matches:
        raise LookupError(f"no lesson folder for chapter {number}")
    return matches[0]


def concept(number: str) -> str:
    """The README's **Concept:** paragraph: what the lesson teaches, in a sentence or two."""
    text = (lesson_dir(number) / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^\*\*Concept:\*\*(.+?)\n\s*\n", text, re.S | re.M)
    if not m:
        raise LookupError(f"lesson {number} README has no **Concept:** line")
    line = _prose(m.group(1))
    return line[0].upper() + line[1:]


def chapter(number: str, title: str, scene: str) -> None:
    """Open a lesson: the title, what it teaches, the files that go with it, and the scene."""
    folder = lesson_dir(number).relative_to(ROOT)
    console.print(Rule(f"[bold]Chapter {number}: {title}[/bold]", style="yellow"))
    console.print(Panel(
        f"[bold]You are learning:[/bold] {concept(number)}\n\n"
        f"[bold]Read alongside:[/bold] {folder}/README.md (concept, diagrams, exercises)\n"
        f"[bold]The code that runs:[/bold] {folder}/run.py (the prompts live here; "
        "the exercises ask you to edit them)\n\n"
        "[dim]The story below is the setting. LANTERN is the local model; the case files are "
        "the text you send it.[/dim]",
        title="What this lesson is for", border_style="blue", padding=(1, 2)))
    console.print(Panel(_prose(scene), title="Case File 01: The Pier 9 Ledger",
                        border_style="yellow", padding=(1, 2)))


def your_turn(number: str, check: list[str], exercises: list[str]) -> None:
    """Close the run: what to check in the replies above, and what to change and rerun."""
    folder = lesson_dir(number).relative_to(ROOT)
    lines = ["[bold]Check the replies above:[/bold]"]
    lines += [f"  {i}. {c}" for i, c in enumerate(check, 1)]
    lines += ["", f"[bold]Then change something and rerun[/bold] "
              f"([cyan]make lesson N={number}[/cyan]):"]
    lines += [f"  {i}. {e}" for i, e in enumerate(exercises, 1)]
    lines += ["", f"[dim]More detail: 'Try this' in {folder}/README.md. "
              f"Undo your edits with: git checkout {folder}/run.py[/dim]"]
    console.print()
    console.print(Panel("\n".join(lines), title="[bold]Your turn[/bold]", border_style="blue",
                        padding=(1, 2)))


def step(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan", align="left"))


def evidence(label: str, text: str) -> None:
    console.print(Panel(text.strip(), title=f"[dim]evidence[/dim] {label}", border_style="dim"))


def reply(label: str, text: str, *, meta: str = "", style: str = "green") -> None:
    console.print(Panel(Markdown(text.strip() or "(empty)"), title=label, subtitle=meta,
                        border_style=style))


def note(text: str) -> None:
    console.print(f"[magenta]>[/magenta] {text}")


def finding(text: str) -> None:
    """Close a lesson: what the evidence now shows."""
    console.print()
    console.print(Panel(_prose(text), title="[bold]What the evidence now shows[/bold]",
                        border_style="red", padding=(1, 2)))


def save_shot(name: str) -> None:
    """Save the recorded terminal output as an SVG screenshot (only with --shot)."""
    if not SHOT:
        return
    out = ROOT / load_config()["screenshots_dir"] / f"{name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(out), title=f"make lesson N={name[:2]}")
    # Fira Code draws "<|" and "|>" as arrows, which mangles chat-template text. Turn it off.
    svg = out.read_text(encoding="utf-8")
    out.write_text(svg.replace("<style>", "<style>\ntext { font-variant-ligatures: none; }", 1),
                   encoding="utf-8")
    console.print(f"[dim]screenshot saved to {out.relative_to(ROOT)}[/dim]")

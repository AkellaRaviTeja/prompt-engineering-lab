"""Chapter 01 reference solution: a precise prompt, built and checked. Compare it with yours."""

from __future__ import annotations

import re

PARTS = ("task", "rules", "format", "evidence")


def build_prompt(
    *,
    task: str,
    evidence: str,
    role: str = "",
    rules: list[str] | tuple[str, ...] = (),
    output_format: str = "",
    tag: str = "statement",
) -> str:
    """A precise prompt: role, task, rules, format, then the evidence inside <tag> ... </tag>."""
    if not task.strip():
        raise ValueError("a prompt needs a task")
    if not evidence.strip():
        raise ValueError("a prompt needs its evidence")
    sections = []
    if role.strip():
        sections.append(role.strip())
    sections.append(f"Task: {task.strip()}")
    if rules:
        sections.append("Rules:\n" + "\n".join(f"- {r.strip()}" for r in rules))
    if output_format.strip():
        sections.append(f"Format: {output_format.strip()}")
    # The evidence cannot close its own block: a tag inside it is neutralised.
    safe = re.sub(rf"<(/?){re.escape(tag)}>", rf"&lt;\1{tag}&gt;", evidence.strip())
    sections.append(f"<{tag}>\n{safe}\n</{tag}>")
    return "\n\n".join(sections)


def check_prompt(prompt: str, tag: str = "statement") -> list[str]:
    """The parts a prompt is missing, from PARTS, in that order. An empty list means complete."""
    missing = []
    if not re.search(r"^Task:\s*\S", prompt, re.M):
        missing.append("task")
    if not re.search(r"^Rules:\s*\n-\s*\S", prompt, re.M):
        missing.append("rules")
    if not re.search(r"^Format:\s*\S", prompt, re.M):
        missing.append("format")
    opens, closes = prompt.count(f"<{tag}>"), prompt.count(f"</{tag}>")
    if not (opens == closes == 1 and prompt.index(f"<{tag}>") < prompt.index(f"</{tag}>")):
        missing.append("evidence")
    return missing

"""Chapter 01 exercise: build the precise prompt, and a check that says what a prompt is missing.

Fill in `build_prompt` and `check_prompt`. Grade them with `make exercise N=01` (offline: no
model is called). Stuck? `make hint N=01`. Start again? `make exercise-reset N=01`.
"""

from __future__ import annotations

import re  # noqa: F401  (the solution uses it)

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
    """A precise prompt: role, task, rules, format, then the evidence inside <tag> ... </tag>.

    The layout, with a blank line between sections and empty sections left out:

        <role>

        Task: <task>

        Rules:
        - <rule 1>
        - <rule 2>

        Format: <output_format>

        <statement>
        <evidence>
        </statement>

    Raise ValueError if the task or the evidence is blank. The evidence goes in word for word,
    except that any <tag> or </tag> inside it becomes &lt;tag&gt; or &lt;/tag&gt;, so a document
    cannot close its own block and smuggle instructions after it.
    """
    # TODO 1: raise ValueError for a blank task or blank evidence.
    # TODO 2: collect the sections in order: role (if any), "Task: ...", "Rules:" with one
    #         "- " line per rule (if any), "Format: ..." (if any).
    # TODO 3: neutralise <tag> and </tag> inside the evidence, then wrap it in the tags.
    # TODO 4: join the sections with a blank line between them.
    raise NotImplementedError("TODO 1 to 4: build the prompt")


def check_prompt(prompt: str, tag: str = "statement") -> list[str]:
    """The parts a prompt is missing, from PARTS, in that order. An empty list means complete.

    task      no line starting "Task:" with something after it
    rules     no "Rules:" line followed by at least one "- " line
    format    no line starting "Format:" with something after it
    evidence  not exactly one <tag> and one </tag>, the opening one first
    """
    # TODO 5: test each part and return the names of the missing ones, in PARTS order.
    raise NotImplementedError("TODO 5: check the prompt")

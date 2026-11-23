"""Chapter 06 exercise: write the reproducibility check.

Hale's question is whether LANTERN gives the same answer twice. `check_reproducible` answers it
for one prompt: run it N times with fixed settings, count the distinct answers, and say whether
the finding reproduces. Grade it with `make exercise N=06` (offline: the tests use a scripted
model).

Stuck? `make hint N=06`. Start again? `make exercise-reset N=06`.
"""

from __future__ import annotations

import hashlib  # noqa: F401  (the solution uses it)
from collections import Counter  # noqa: F401
from collections.abc import Callable
from typing import Any


def check_reproducible(
    prompt: str,
    *,
    chat: Callable[..., Any],
    runs: int = 5,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send the same prompt `runs` times with the same settings and report what came back.

    `chat(prompt, **settings)` returns a reply with `.text`. Answers are compared after
    stripping leading and trailing whitespace, so "KB 714 FLR\\n" and "KB 714 FLR" are one answer.

    Return a dict:
        answers        every answer, stripped, in the order they came back
        distinct       how many different answers there were
        counts         {answer: how many times it came back}
        most_common    the answer that came back most often
        agreement      the share of runs that gave most_common (0 to 1)
        reproducible   True only if every run gave the same answer
        settings       the settings every run used (a copy)
        prompt_sha256  the SHA-256 of the prompt, hex, so the record names exactly what was asked

    Raise ValueError if runs < 2: one run cannot show anything reproduces.
    """
    # TODO 1: refuse runs < 2 with a ValueError that says why.
    # TODO 2: call chat(prompt, **settings) `runs` times with the same settings, and keep each
    #         reply's text, stripped.
    # TODO 3: count the answers (collections.Counter) and find the most common one.
    # TODO 4: build and return the dict described above.
    raise NotImplementedError("TODO 1 to 4: the reproducibility check")

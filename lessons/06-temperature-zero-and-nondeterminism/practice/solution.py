"""Chapter 06 reference solution: the reproducibility check. Compare it with yours after trying."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from typing import Any


def check_reproducible(
    prompt: str,
    *,
    chat: Callable[..., Any],
    runs: int = 5,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send the same prompt `runs` times with the same settings and report what came back."""
    if runs < 2:
        raise ValueError("one run cannot show that a finding reproduces: use runs >= 2")
    settings = dict(settings or {})
    answers = [chat(prompt, **settings).text.strip() for _ in range(runs)]
    counts = Counter(answers)
    most_common, n = counts.most_common(1)[0]
    return {
        "answers": answers,
        "distinct": len(counts),
        "counts": dict(counts),
        "most_common": most_common,
        "agreement": n / runs,
        "reproducible": len(counts) == 1,
        "settings": settings,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }

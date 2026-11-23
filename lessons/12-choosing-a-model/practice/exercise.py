"""Chapter 12 exercise: the model scorecard.

A model choice you can defend is a table: how often it was right, how long the user waited
(the median and the slow tail), and what each right answer cost. Write the function that turns a
list of answered questions into that table. Chapter 12's run.py builds its scorecard the same way.

Grade it with `make exercise N=12` (offline, no model). Stuck? `make hint N=12`.
Start again? `make exercise-reset N=12`.
"""

from __future__ import annotations

import math  # noqa: F401  (the solution uses it)
from typing import Any


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: the smallest value with at least q% of the values at or below it.

    percentile([4, 1, 3, 2], 50) == 2; percentile(sixteen values, 95) is the largest.
    Raises ValueError on an empty list.
    """
    # TODO 1: refuse an empty list. Sort the values.
    # TODO 2: the rank is ceil(q / 100 * n), at least 1. Return the value at that rank (1-based).
    raise NotImplementedError("TODO 1 and 2: percentile")


def scorecard(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per model, in the order models first appear.

    Each input row is one answered question: {"model": str, "correct": bool, "seconds": float
    (wall clock, load and prompt processing included), "cost_usd": float or None (None when the
    model has no checked price)}.

    Each output row: {"model", "n", "accuracy" (correct / n), "p50_s", "p95_s",
    "cost_per_correct" (total cost / correct answers; None when any cost is unknown or nothing
    was correct)}. Raises ValueError on no rows.
    """
    # TODO 3: refuse an empty list. Group the rows by model, keeping first-seen order.
    # TODO 4: accuracy, and p50 and p95 of seconds with percentile().
    # TODO 5: cost per correct answer. An unknown price is unknown, never 0; no correct
    #         answers is None, never a division by zero.
    raise NotImplementedError("TODO 3 to 5: scorecard")

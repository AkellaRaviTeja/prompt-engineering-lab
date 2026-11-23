"""Chapter 12 solution: the model scorecard. Read it once you have tried."""

from __future__ import annotations

import math
from typing import Any


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: the smallest value with at least q% of the values at or below it.

    percentile([4, 1, 3, 2], 50) == 2; percentile(sixteen values, 95) is the largest.
    Raises ValueError on an empty list.
    """
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    return ordered[max(math.ceil(q / 100 * len(ordered)), 1) - 1]


def scorecard(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per model, in the order models first appear.

    Each input row is one answered question: {"model": str, "correct": bool, "seconds": float
    (wall clock, load and prompt processing included), "cost_usd": float or None (None when the
    model has no checked price)}.

    Each output row: {"model", "n", "accuracy" (correct / n), "p50_s", "p95_s",
    "cost_per_correct" (total cost / correct answers; None when any cost is unknown or nothing
    was correct)}. Raises ValueError on no rows.
    """
    if not rows:
        raise ValueError("no results to score")
    out = []
    for model in dict.fromkeys(r["model"] for r in rows):
        mine = [r for r in rows if r["model"] == model]
        right = sum(bool(r["correct"]) for r in mine)
        costs = [r["cost_usd"] for r in mine]
        seconds = [r["seconds"] for r in mine]
        unknown = any(c is None for c in costs)
        out.append({
            "model": model,
            "n": len(mine),
            "accuracy": right / len(mine),
            "p50_s": percentile(seconds, 50),
            "p95_s": percentile(seconds, 95),
            "cost_per_correct": None if unknown or right == 0 else sum(costs) / right,
        })
    return out

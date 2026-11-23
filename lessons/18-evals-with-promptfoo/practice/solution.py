"""Chapter 18 solution: the suite's assertions, written as code."""

from __future__ import annotations

import json
import re
from typing import Any

METRICS = ("valid_json", "invoice_id", "total_matches_ledger")


def grade_extraction(output: str, ref: str, ledger_total: float) -> dict[str, bool]:
    """Grade one extract-invoice output the way evals/tests/extraction.yaml does."""
    try:
        obj = json.loads(output)
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        return dict.fromkeys(METRICS, False)
    total = obj.get("total")
    is_number = isinstance(total, (int, float)) and not isinstance(total, bool)
    return {
        "valid_json": True,
        "invoice_id": obj.get("invoice_id") == ref,
        "total_matches_ledger": is_number and abs(total - ledger_total) < 0.01,
    }


def grade_label(output: str, label: str) -> bool:
    """Grade one classify output the way evals/tests/classification.yaml does."""
    return re.sub(r"[^a-z]", "", output.lower()) == label


def score(cells: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Per named metric, [passed, run] over many extraction cells."""
    out = {m: [0, 0] for m in METRICS}
    for cell in cells:
        for metric, ok in grade_extraction(cell["output"], cell["ref"],
                                           cell["ledger_total"]).items():
            out[metric][0] += ok
            out[metric][1] += 1
    return out

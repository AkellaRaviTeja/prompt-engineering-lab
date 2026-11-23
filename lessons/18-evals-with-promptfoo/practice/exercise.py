"""Chapter 18 exercise: the suite's assertions, written as code.

promptfoo's `is-json` and `javascript` assertions are small functions of the output and the
test's expected values. Write them in Python: one grader for the extraction suite, one for the
classification suite. Each returns a verdict per named metric, the way promptfoo scores a cell.

Grade it with `make exercise N=18` (offline: no model, no promptfoo).
Stuck? `make hint N=18`. Start again? `make exercise-reset N=18`.
"""

from __future__ import annotations

import json
import re
from typing import Any


def grade_extraction(output: str, ref: str, ledger_total: float) -> dict[str, bool]:
    """Grade one extract-invoice output the way evals/tests/extraction.yaml does.

    Return {"valid_json": ..., "invoice_id": ..., "total_matches_ledger": ...}:
        valid_json            the whole output parses as one JSON object (no code fences, no
                              prose around it: the schema-constrained path never adds any)
        invoice_id            the object's invoice_id is exactly `ref`
        total_matches_ledger  the object's total is a number within 0.01 of `ledger_total`

    Output that is not a JSON object fails all three. A total that is not a number (a string
    such as "94000.00", a boolean, null, or missing) fails total_matches_ledger and must not
    raise. The suite's javascript checks `typeof total === 'number'` for the same reason: without
    it, Number("94000.00") would quietly turn a string into a pass.
    """
    # TODO 1: parse `output` with json.loads. On ValueError, or if the result is not a dict,
    #         return all three metrics False.
    # TODO 2: invoice_id: compare the object's "invoice_id" with `ref`, exactly.
    # TODO 3: total_matches_ledger: accept only an int or float (not bool), then compare with
    #         abs(total - ledger_total) < 0.01.
    raise NotImplementedError("TODO 1 to 3: grade one extraction output")


def grade_label(output: str, label: str) -> bool:
    """Grade one classify output the way evals/tests/classification.yaml does.

    The output passes when, lower-cased and with every character that is not a letter a to z
    removed, it equals `label`. "Threat." and " THREAT\\n" pass for "threat"; "It is a threat"
    and "threat/logistics" do not: a classifier that explains itself has not followed the
    instruction to reply with the label only.
    """
    # TODO 4: lower-case, drop everything that is not a to z (re.sub), compare with `label`.
    raise NotImplementedError("TODO 4: grade one classification output")


def score(cells: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Per named metric, [passed, run] over many extraction cells.

    Each cell is {"output": str, "ref": str, "ledger_total": float}. This is promptfoo's
    "named metrics" view: one row per property, not per test.
    """
    # TODO 5: run grade_extraction on every cell and add up passes and runs per metric.
    raise NotImplementedError("TODO 5: score per named metric")


# Keep the imports the solution needs.
_ = (json, re)

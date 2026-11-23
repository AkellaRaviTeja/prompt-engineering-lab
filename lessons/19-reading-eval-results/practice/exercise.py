"""Chapter 19 exercise: triage an eval's failures.

A pass rate says whether to look. The pattern of a test's failures across models says where:
some cells (a prompt or a model), every cell with different answers (a hard task or a debatable
label), or every cell with the same answer (suspect the expected value). Write the triage.

Grade it with `make exercise N=19` (offline: hand-made promptfoo rows, no model).
Then `make lesson N=19 ARGS=--mine` runs the lesson's step 4 on your triage.
Stuck? `make hint N=19`. Start again? `make exercise-reset N=19`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def answer_key(row: dict[str, Any]) -> str:
    """The part of a cell's output the test cares about, normalised so equal answers compare
    equal: "total=94000.00" for an extraction, the letters of the reply otherwise. Given."""
    out = ((row.get("response") or {}).get("output") or "").strip()
    try:
        return f"total={float(json.loads(out)['total']):.2f}"
    except (ValueError, KeyError, TypeError):
        return "".join(c for c in out.lower() if c.isalpha())[:24]


def triage(rows: list[dict[str, Any]], key=answer_key) -> list[dict[str, Any]]:
    """Group failing cells by test, across models and prompts, and flag reference-data suspects.

    `rows` are promptfoo results (evals/output/results.json, ["results"]["results"]): each has
    row["testCase"]["description"], row["provider"]["label"] (the model), row["success"] and
    row["response"]["output"].

    Return one dict per test that failed in at least one cell, sorted by most failed cells
    first, then by test name:
        test        the test's description
        failed      how many of its cells failed
        cells       how many cells it ran in
        answers     the distinct key(row) values of its failed cells, sorted
        every_cell  True when it failed in every cell it ran in
        suspect     True when it failed in every cell, on at least two different models, and
                    every failed cell gave the same answer: models that differ do not make the
                    same mistake, so suspect the expected value
    Tests that passed everywhere are left out.
    """
    # TODO 1: one pass over rows: count cells per test, collect the models per test, and the
    #         key(row) of every failed cell per test.
    # TODO 2: for each test with a failed cell, build the dict above. A test seen on one model
    #         only is never a suspect, however it failed.
    # TODO 3: sort by (-failed, test) and return.
    raise NotImplementedError("TODO 1 to 3: triage the failures")


def suspects(rows: list[dict[str, Any]], key=answer_key) -> list[str]:
    """The names of the tests flagged as reference-data suspects, in triage order."""
    # TODO 4: use triage().
    raise NotImplementedError("TODO 4: the suspects")


# Keep the imports the solution needs.
_ = defaultdict

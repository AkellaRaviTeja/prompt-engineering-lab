"""Chapter 19 solution: triage an eval's failures."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def answer_key(row: dict[str, Any]) -> str:
    """The part of a cell's output the test cares about, normalised so equal answers compare
    equal."""
    out = ((row.get("response") or {}).get("output") or "").strip()
    try:
        return f"total={float(json.loads(out)['total']):.2f}"
    except (ValueError, KeyError, TypeError):
        return "".join(c for c in out.lower() if c.isalpha())[:24]


def triage(rows: list[dict[str, Any]], key=answer_key) -> list[dict[str, Any]]:
    """Group failing cells by test, across models and prompts, and flag reference-data suspects."""
    cells: dict[str, int] = defaultdict(int)
    models: dict[str, set[str]] = defaultdict(set)
    failed: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        test = row["testCase"]["description"]
        cells[test] += 1
        models[test].add(row["provider"].get("label") or row["provider"]["id"])
        if not row["success"]:
            failed[test].append(key(row))
    out = []
    for test, answers in failed.items():
        every = len(answers) == cells[test]
        out.append({
            "test": test,
            "failed": len(answers),
            "cells": cells[test],
            "answers": sorted(set(answers)),
            "every_cell": every,
            "suspect": every and len(set(answers)) == 1 and len(models[test]) >= 2,
        })
    return sorted(out, key=lambda t: (-t["failed"], t["test"]))


def suspects(rows: list[dict[str, Any]], key=answer_key) -> list[str]:
    """The names of the tests flagged as reference-data suspects, in triage order."""
    return [t["test"] for t in triage(rows, key) if t["suspect"]]

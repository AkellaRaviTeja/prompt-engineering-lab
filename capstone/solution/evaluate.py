"""The eval suite: run a prompt version over the golden cases and grade every field with code.

    report = evaluate("extract-invoice", "v1", golden.build("extract-invoice"))
    report["score"], report["fields"], report["invalid"]

A case passes when every field is right. A case whose reply never validated counts as invalid
and as failed. The report is plain JSON, so the gate can compare a saved baseline with a fresh
candidate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipeline import run_task


def _name(s: str) -> str:
    return re.sub(r"[^\w ]", "", " ".join(str(s).split())).lower()


def grade(task: str, expected: dict[str, Any], got: dict[str, Any] | None) -> dict[str, bool]:
    """One bool per expected field. `got` is None when the reply never validated."""
    if got is None:
        return {k: False for k in expected}
    if task == "extract-invoice":
        return {
            "invoice_id": got.get("invoice_id") == expected["invoice_id"],
            "vendor": _name(got.get("vendor", "")) == _name(expected["vendor"]),
            "date": str(got.get("date")) == expected["date"],
            "total": isinstance(got.get("total"), int | float)
            and abs(got["total"] - expected["total"]) < 0.005,
        }
    if task == "classify-message":
        return {"label": got.get("label") == expected["label"]}
    raise LookupError(f"no grader for {task!r}")


def evaluate(
    task: str,
    version: str,
    cases: list[dict[str, Any]],
    *,
    chat: Callable[..., Any] | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Run every case through the pipeline at `version` and grade it."""
    if not cases:
        raise ValueError("no cases to evaluate")
    rows = []
    calls = 0
    for case in cases:
        result = run_task(task, version, case["input"], chat=chat, max_attempts=max_attempts)
        calls += result.attempts
        got = result.value.model_dump(mode="json") if result.ok else None
        fields = grade(task, case["expected"], got)
        rows.append({
            "id": case["id"],
            "passed": all(fields.values()),
            "valid": result.ok,
            "attempts": result.attempts,
            "fields": fields,
            "got": got,
            "expected": case["expected"],
        })
    n = len(rows)
    names = list(rows[0]["fields"])
    passed = sum(r["passed"] for r in rows)
    return {
        "task": task,
        "version": version,
        "prompt": f"{task}@{version}",
        "n": n,
        "passed": passed,
        "score": passed / n,
        "invalid": sum(not r["valid"] for r in rows),
        "calls": calls,
        "fields": {f: sum(r["fields"][f] for r in rows) / n for f in names},
        "cases": rows,
    }


def save(report: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

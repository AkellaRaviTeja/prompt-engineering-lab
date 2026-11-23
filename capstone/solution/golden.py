"""The golden set: test cases built by code from the case files, never by the model.

Invoice truth comes from the paper invoice (case/invoices/*.txt). The vendor's name is taken
from the ledger row with the same reference, because the ledger writes it in normal
capitalisation. The ledger's amount is kept beside the case as `ledger_total` but is never the
expected answer: chapter 19 showed that one ledger row was altered after seizure.

Message truth is the gold label in case/messages.jsonl.

    build("extract-invoice")   # 8 cases
    build("classify-message")  # 48 cases
    case = {"id": "NW-0419", "input": {"invoice": "..."},
            "expected": {"invoice_id": "NW-0419", "vendor": "Northwind Freight Ltd",
                         "date": "2026-03-03", "total": 94000.0},
            "ledger_total": 9400.0}
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

CASE = Path(__file__).resolve().parents[2] / "case"


def _field(pattern: str, text: str, path: Path) -> str:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise ValueError(f"{path.name}: no match for {pattern!r}")
    return m.group(1).strip()


def invoice_cases(case_dir: Path) -> list[dict[str, Any]]:
    with open(case_dir / "ledger.csv", newline="", encoding="utf-8") as f:
        ledger = {row["reference"]: row for row in csv.DictReader(f)}
    cases = []
    for path in sorted((case_dir / "invoices").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        invoice_id = _field(r"^INVOICE\s+(\S+)", text, path)
        letterhead = text.splitlines()[0].strip()
        row = ledger.get(invoice_id)
        if row is None:
            raise ValueError(f"{path.name}: no ledger row with reference {invoice_id}")
        if row["payee"].lower() != letterhead.lower():
            raise ValueError(f"{path.name}: letterhead {letterhead!r} is not {row['payee']!r}")
        cases.append({
            "id": invoice_id,
            "input": {"invoice": text},
            "expected": {
                "invoice_id": invoice_id,
                "vendor": row["payee"],
                "date": _field(r"^Date:\s*(\S+)", text, path),
                "total": float(_field(r"^Total due:\s*([\d,]+\.\d{2})", text, path)
                               .replace(",", "")),
            },
            "ledger_total": float(row["amount_kbd"]),
        })
    return cases


def message_cases(case_dir: Path) -> list[dict[str, Any]]:
    cases = []
    with open(case_dir / "messages.jsonl", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            m = json.loads(line)
            cases.append({
                "id": m["id"],
                "input": {"sender": m["from"], "text": m["text"]},
                "expected": {"label": m["label"]},
            })
    return sorted(cases, key=lambda c: c["id"])


BUILDERS = {"extract-invoice": invoice_cases, "classify-message": message_cases}


def build(task: str, case_dir: Path | None = None) -> list[dict[str, Any]]:
    """The golden cases for one task, sorted by id."""
    if task not in BUILDERS:
        raise LookupError(f"no golden set for {task!r}; tasks: {', '.join(BUILDERS)}")
    cases = BUILDERS[task](Path(case_dir) if case_dir else CASE)
    if not cases:
        raise ValueError(f"the golden set for {task} is empty")
    return cases

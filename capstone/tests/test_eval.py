"""The golden set, built by code from the case files, and the eval that grades against it."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from lantern.testing import Scripted, say

CASE = Path(__file__).resolve().parents[2] / "case"


def test_golden_invoices(golden):
    """Eight invoice cases, sorted by id, with the totals from the paper, not the ledger."""
    cases = golden.build("extract-invoice", CASE)
    ids = [c["id"] for c in cases]
    assert len(cases) == 8, f"eight invoices in case/invoices, got {len(cases)}"
    assert ids == sorted(ids), f"cases are sorted by id: {ids}"
    nw = next(c for c in cases if c["id"] == "NW-0419")
    assert nw["expected"] == {"invoice_id": "NW-0419", "vendor": "Northwind Freight Ltd",
                              "date": "2026-03-03", "total": 94000.0}, nw["expected"]
    assert nw["ledger_total"] == 9400.0, "the ledger's (altered) amount is kept beside the case"
    assert "INVOICE NW-0419" in nw["input"]["invoice"], "the input is the invoice text"


def test_golden_messages(golden):
    """48 message cases with their gold labels: 20 logistics, 16 personal, 12 threat."""
    cases = golden.build("classify-message", CASE)
    assert len(cases) == 48, f"48 messages, got {len(cases)}"
    counts = Counter(c["expected"]["label"] for c in cases)
    assert counts == {"logistics": 20, "personal": 16, "threat": 12}, f"labels: {counts}"
    m03 = next(c for c in cases if c["id"] == "M03")
    assert m03["input"] == {"sender": "unknown +88 301",
                            "text": "You asked about Northwind. Some questions are expensive."}, (
        m03["input"])


def test_unknown_task_has_no_golden_set(golden):
    """build() refuses a task it has no cases for."""
    with pytest.raises(LookupError):
        golden.build("summarise", CASE)


EXPECTED = {"invoice_id": "NW-0419", "vendor": "Northwind Freight Ltd",
            "date": "2026-03-03", "total": 94000.0}


def test_grade_invoice_fields(evaluate):
    """The code grader checks each field; vendor ignores case, total must match to the cent."""
    g = evaluate.grade("extract-invoice", EXPECTED, dict(EXPECTED))
    assert all(g.values()) and set(g) == set(EXPECTED), f"an exact copy passes: {g}"
    g = evaluate.grade("extract-invoice", EXPECTED, {**EXPECTED, "vendor": "NORTHWIND FREIGHT LTD"})
    assert g["vendor"], "the letterhead's capitals are the same vendor"
    g = evaluate.grade("extract-invoice", EXPECTED, {**EXPECTED, "total": 9400.0})
    assert not g["total"] and g["invoice_id"], f"the ledger's 9,400 is wrong: {g}"
    g = evaluate.grade("extract-invoice", EXPECTED, {**EXPECTED, "date": "2026-03-04"})
    assert not g["date"], "a different date fails"
    g = evaluate.grade("extract-invoice", EXPECTED, None)
    assert not any(g.values()), f"no valid reply fails every field: {g}"


def test_grade_message_label(evaluate):
    """The message grader compares the label exactly."""
    assert evaluate.grade("classify-message", {"label": "threat"}, {"label": "threat"}) == {
        "label": True}
    assert evaluate.grade("classify-message", {"label": "threat"}, {"label": "personal"}) == {
        "label": False}


def test_evaluate_scores_a_run(evaluate, golden):
    """evaluate() runs every case, counts passes, invalid replies and calls, per field too."""
    cases = golden.build("extract-invoice", CASE)[:3]
    right = say(json.dumps(cases[0]["expected"]))
    wrong = say(json.dumps({**cases[1]["expected"], "total": 1.0}))
    bad = say("I cannot read this invoice.")
    model = Scripted([right, wrong, bad, bad, bad])
    r = evaluate.evaluate("extract-invoice", "v1", cases, chat=model)
    assert model.calls == 5, f"1 + 1 + 3 attempts, got {model.calls} calls"
    assert (r["n"], r["passed"], r["invalid"], r["calls"]) == (3, 1, 1, 5), (
        f"n, passed, invalid, calls: {r['n']}, {r['passed']}, {r['invalid']}, {r['calls']}")
    assert r["score"] == pytest.approx(1 / 3), f"score is passed / n, got {r['score']}"
    assert r["fields"]["total"] == pytest.approx(1 / 3), f"fields: {r['fields']}"
    assert r["fields"]["invoice_id"] == pytest.approx(2 / 3), f"fields: {r['fields']}"
    assert [c["passed"] for c in r["cases"]] == [True, False, False], r["cases"]
    assert r["task"] == "extract-invoice" and r["version"] == "v1", "the report names its prompt"
    json.dumps(r)  # the gate reads saved reports, so a report must be plain JSON


def test_evaluate_messages(evaluate, golden):
    """evaluate() grades the message task at the version asked for."""
    cases = golden.build("classify-message", CASE)[:4]
    labels = [c["expected"]["label"] for c in cases]
    replies = [say(json.dumps({"label": lab})) for lab in labels[:3]]
    replies.append(say(json.dumps({"label": "threat" if labels[3] != "threat" else "personal"})))
    model = Scripted(replies)
    r = evaluate.evaluate("classify-message", "v2", cases, chat=model)
    assert r["score"] == pytest.approx(0.75), f"3 of 4 right, got {r['score']}"
    assert {q.get("prompt_version") for q in model.requests} == {"classify-message@v2"}, (
        "every eval call is logged with the version under test")

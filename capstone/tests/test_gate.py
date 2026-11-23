"""The CI gate: an equal candidate passes, a regression beyond the tolerance fails."""

from __future__ import annotations

import json
from pathlib import Path

from lantern.testing import Scripted, say

CASE = Path(__file__).resolve().parents[2] / "case"


def report(score_of, invalid=0, version="v1", task="classify-message"):
    """A saved eval report with ten cases, the first `score_of` passing."""
    cases = [{"id": f"M{i:02d}", "passed": i <= score_of, "valid": i <= 10 - invalid,
              "attempts": 1, "fields": {"label": i <= score_of}} for i in range(1, 11)]
    return {"task": task, "version": version, "prompt": f"{task}@{version}", "n": 10,
            "passed": score_of, "score": score_of / 10, "invalid": invalid, "calls": 10,
            "fields": {"label": score_of / 10}, "cases": cases}


def test_equal_candidate_passes(gate):
    """A candidate that scores the same as the baseline passes."""
    ok, lines = gate.compare(report(8), report(8, version="v2"), 0.0)
    assert ok, f"an equal candidate must pass: {lines}"
    assert lines, "the gate prints what it checked"


def test_regression_beyond_tolerance_fails(gate):
    """A drop larger than the tolerance fails; a drop inside it passes."""
    ok, lines = gate.compare(report(8), report(6, version="v2"), 0.1)
    assert not ok, f"a 0.2 drop with tolerance 0.1 must fail: {lines}"
    ok, lines = gate.compare(report(8), report(7, version="v2"), 0.1)
    assert ok, f"a 0.1 drop with tolerance 0.1 passes: {lines}"


def test_more_invalid_replies_fail(gate):
    """A candidate whose replies stop validating fails even when the score holds."""
    ok, lines = gate.compare(report(7), report(7, invalid=3, version="v2"), 0.1)
    assert not ok, f"three more invalid replies in ten must fail: {lines}"


def test_gate_refuses_what_it_cannot_compare(gate):
    """No cases, different tasks or different golden cases never pass."""
    empty = {**report(0), "n": 0, "cases": []}
    assert not gate.compare(empty, empty, 0.1)[0], "an empty report must not pass"
    other = report(8, task="extract-invoice")
    assert not gate.compare(report(8), other, 0.1)[0], "different tasks must not pass"
    shifted = report(8)
    shifted["cases"] = shifted["cases"][1:] + shifted["cases"][:1]
    assert not gate.compare(report(8), shifted, 0.1)[0], "different case lists must not pass"


def test_gate_exit_codes_from_saved_reports(gate, tmp_path):
    """main() exits 0 for an equal candidate and 1 for a regression, from saved reports."""
    base, same, worse = tmp_path / "b.json", tmp_path / "s.json", tmp_path / "w.json"
    base.write_text(json.dumps(report(9)))
    same.write_text(json.dumps(report(9, version="v2")))
    worse.write_text(json.dumps(report(5, version="v2")))
    args = ["classify-message", "--baseline", "v1", "--candidate", "v2", "--tolerance", "0.05",
            "--baseline-report", str(base)]
    assert gate.main([*args, "--candidate-report", str(same)]) == 0, "equal must exit 0"
    assert gate.main([*args, "--candidate-report", str(worse)]) == 1, "regression must exit 1"


def test_gate_runs_the_eval(gate, golden, tmp_path):
    """Without saved reports, main() runs both versions on the golden set through `chat`."""
    cases = golden.build("extract-invoice", CASE)[:2]
    answers = [say(json.dumps(c["expected"])) for c in cases]
    model = Scripted(answers * 2)
    code = gate.main(["extract-invoice", "--baseline", "v1", "--candidate", "v1",
                      "--limit", "2", "--out", str(tmp_path)], chat=model)
    assert code == 0, f"the same version against itself must pass, exit {code}"
    assert model.calls == 4, f"two cases, two runs: 4 calls, got {model.calls}"
    assert {r.get("prompt_version") for r in model.requests} == {"extract-invoice@v1"}
    saved = list(tmp_path.glob("*.json"))
    assert saved, "with --out the gate saves its reports"


def test_gate_fails_a_bad_candidate_run(gate, golden):
    """A candidate run that gets the totals wrong fails the gate with exit 1."""
    cases = golden.build("extract-invoice", CASE)[:2]
    good = [say(json.dumps(c["expected"])) for c in cases]
    wrong = [say(json.dumps({**c["expected"], "total": 0.5})) for c in cases]
    model = Scripted(good + wrong)
    code = gate.main(["extract-invoice", "--baseline", "v1", "--candidate", "v1",
                      "--limit", "2"], chat=model)
    assert code == 1, f"a candidate that loses every total must exit 1, got {code}"

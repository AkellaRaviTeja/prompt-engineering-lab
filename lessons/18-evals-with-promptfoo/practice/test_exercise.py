"""Chapter 18: assertions as code. The first docstring line is what `make exercise` shows."""

import json

NW0419 = json.dumps({"invoice_id": "NW-0419", "vendor": "Northwind Freight Ltd",
                     "date": "2026-02-12", "total": 94000.0})


def test_a_correct_extraction_passes_every_metric(impl):
    """A JSON object with the right id and total passes all three metrics."""
    out = impl.grade_extraction(NW0419, "NW-0419", 94000.0)
    assert out == {"valid_json": True, "invoice_id": True, "total_matches_ledger": True}, (
        f"expected all three metrics to pass, got {out}")


def test_the_total_is_checked_against_the_ledger_value(impl):
    """A total that differs from the expected value fails only total_matches_ledger."""
    out = impl.grade_extraction(NW0419, "NW-0419", 9400.0)
    assert out["valid_json"] and out["invoice_id"], "the JSON and the id are still right"
    assert out["total_matches_ledger"] is False, "94000 is not within 0.01 of 9400"


def test_the_tolerance_is_one_cent(impl):
    """A total within 0.01 passes; one 0.02 away fails."""
    near = json.dumps({"invoice_id": "NW-0388", "total": 62500.005})
    far = json.dumps({"invoice_id": "NW-0388", "total": 62500.02})
    assert impl.grade_extraction(near, "NW-0388", 62500.0)["total_matches_ledger"] is True, (
        "62500.005 is within 0.01 of 62500")
    assert impl.grade_extraction(far, "NW-0388", 62500.0)["total_matches_ledger"] is False, (
        "62500.02 is more than 0.01 away")


def test_fenced_or_wrapped_json_is_not_valid(impl):
    """Code fences or prose around the JSON fail everything: no transform hides them."""
    for bad in ("```json\n" + NW0419 + "\n```", "Here it is: " + NW0419, "[1, 2]", ""):
        out = impl.grade_extraction(bad, "NW-0419", 94000.0)
        assert not any(out.values()), f"{bad[:20]!r} should fail all three metrics, got {out}"


def test_a_total_that_is_not_a_number_fails_without_raising(impl):
    """A total given as a string, a boolean, null or not at all fails, and does not crash."""
    for total in ("94000.00", "94,000.00", True, None):
        out = impl.grade_extraction(json.dumps({"invoice_id": "NW-0419", "total": total}),
                                    "NW-0419", 94000.0)
        assert out["total_matches_ledger"] is False, f"total={total!r} must not count as a match"
    out = impl.grade_extraction('{"invoice_id": "NW-0419"}', "NW-0419", 94000.0)
    assert out["total_matches_ledger"] is False, "a missing total must fail"


def test_the_id_must_match_exactly(impl):
    """'INVOICE NW-0419' or a lower-case id is not the reference."""
    for ref_out in ("INVOICE NW-0419", "nw-0419", "NW-419"):
        out = impl.grade_extraction(json.dumps({"invoice_id": ref_out, "total": 94000}),
                                    "NW-0419", 94000.0)
        assert out["invoice_id"] is False, f"{ref_out!r} is not NW-0419"


def test_label_grader_ignores_case_and_punctuation_only(impl):
    """'Threat.' passes for threat; an explanation or two labels do not."""
    assert impl.grade_label("Threat.", "threat") and impl.grade_label(" THREAT\n", "threat"), (
        "case and punctuation around the label are allowed")
    for bad in ("It is a threat", "threat/logistics", "The message is **not a threat**"):
        assert impl.grade_label(bad, "threat") is False, f"{bad!r} is not a one-word label"
    assert impl.grade_label("logistics", "threat") is False, "the wrong label fails"


def test_score_counts_passes_per_metric(impl):
    """score() gives [passed, run] per metric over every cell."""
    cells = [
        {"output": NW0419, "ref": "NW-0419", "ledger_total": 9400.0},
        {"output": json.dumps({"invoice_id": "NW-0388", "total": 62500}), "ref": "NW-0388",
         "ledger_total": 62500.0},
        {"output": "not json", "ref": "NW-0402", "ledger_total": 71200.0},
    ]
    out = impl.score(cells)
    assert out == {"valid_json": [2, 3], "invoice_id": [2, 3],
                   "total_matches_ledger": [1, 3]}, f"per-metric counts were {out}"

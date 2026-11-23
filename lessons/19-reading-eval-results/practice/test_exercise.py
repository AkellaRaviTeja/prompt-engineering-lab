"""Chapter 19: failure triage. Each test's first docstring line is what `make exercise` shows."""

import json


def cell(test, model, ok, output, prompt="p"):
    """One promptfoo result row, in the shape of evals/output/results.json."""
    return {"testCase": {"description": test}, "provider": {"id": f"x:{model}", "label": model},
            "prompt": {"label": prompt}, "success": ok, "response": {"output": output}}


def total(t):
    return json.dumps({"invoice_id": "NW-0419", "total": t})


ROWS = [
    # every model, same total: the reference is the suspect
    cell("extract NW-0419", "qwen3-1.7b", False, total(94000)),
    cell("extract NW-0419", "qwen3-0.6b", False, total(94000.0)),
    # passes everywhere
    cell("extract NW-0388", "qwen3-1.7b", True, total(62500)),
    cell("extract NW-0388", "qwen3-0.6b", True, total(62500)),
    # every cell, different answers: a hard test
    cell("classify M36", "qwen3-1.7b", False, "logistics", "v1"),
    cell("classify M36", "qwen3-0.6b", False, "personal", "v1"),
    cell("classify M36", "qwen3-1.7b", False, "logistics", "v2"),
    # some cells: a prompt or a model problem
    cell("classify M40", "qwen3-1.7b", True, "personal", "v2"),
    cell("classify M40", "qwen3-0.6b", False, "threat", "v1"),
]


def by_test(out):
    return {t["test"]: t for t in out}


def test_only_failing_tests_are_listed(impl):
    """A test that passed in every cell is left out."""
    out = by_test(impl.triage(ROWS))
    assert "extract NW-0388" not in out, "NW-0388 passed everywhere and should not be listed"
    assert set(out) == {"extract NW-0419", "classify M36", "classify M40"}, (
        f"listed {sorted(out)}")


def test_failed_and_cells_are_counted_per_test_across_models(impl):
    """failed and cells count every cell of the test, across models and prompts."""
    out = by_test(impl.triage(ROWS))
    got = {k: (v["failed"], v["cells"]) for k, v in out.items()}
    assert got == {"extract NW-0419": (2, 2), "classify M36": (3, 3), "classify M40": (1, 2)}, (
        f"(failed, cells) per test were {got}")


def test_same_answer_on_every_model_is_a_suspect(impl):
    """Failing everywhere with one answer, on two models, flags a reference-data suspect."""
    t = by_test(impl.triage(ROWS))["extract NW-0419"]
    assert t["every_cell"] and t["suspect"], f"NW-0419 should be a suspect, got {t}"
    assert t["answers"] == ["total=94000.00"], (
        f"94000 and 94000.0 are one answer; got {t['answers']}")


def test_different_answers_or_some_cells_are_not_suspects(impl):
    """Different wrong answers, or a test that passes somewhere, is not a suspect."""
    out = by_test(impl.triage(ROWS))
    assert out["classify M36"]["every_cell"] and not out["classify M36"]["suspect"], (
        "M36 failed everywhere but with different answers: a hard test, not bad data")
    assert out["classify M36"]["answers"] == ["logistics", "personal"], "distinct answers, sorted"
    assert not out["classify M40"]["every_cell"] and not out["classify M40"]["suspect"], (
        "M40 passed in one cell: a prompt or model problem")


def test_one_model_is_never_enough(impl):
    """A test run on one model only is not a suspect, even if every cell agrees."""
    rows = [cell("extract X", "qwen3-1.7b", False, total(5), "v1"),
            cell("extract X", "qwen3-1.7b", False, total(5), "v2")]
    t = impl.triage(rows)[0]
    assert t["every_cell"] and not t["suspect"], (
        "with one model there is nothing to compare: the agreement could be its own blind spot")


def test_sorted_by_most_failed_then_name(impl):
    """Most failed cells first; ties in name order."""
    rows = ROWS + [cell("classify M30", "qwen3-1.7b", False, "x", "v1"),
                   cell("classify M30", "qwen3-0.6b", False, "y", "v1")]
    order = [t["test"] for t in impl.triage(rows)]
    assert order == ["classify M36", "classify M30", "extract NW-0419", "classify M40"], (
        f"order was {order}")


def test_suspects_lists_the_flagged_tests(impl):
    """suspects() returns only the reference-data suspects."""
    assert impl.suspects(ROWS) == ["extract NW-0419"], f"got {impl.suspects(ROWS)}"
    fixed = [r for r in ROWS if r["testCase"]["description"] != "extract NW-0419"]
    assert impl.suspects(fixed) == [], "with NW-0419 gone there is nothing to suspect"


def test_the_answer_key_is_a_parameter(impl):
    """triage(key=...) uses the key it is given to compare answers."""
    out = by_test(impl.triage(ROWS, key=lambda r: r["response"]["output"]))
    assert not out["extract NW-0419"]["suspect"], (
        "compared as raw text, '94000' and '94000.0' differ: the key decides what 'same' means")

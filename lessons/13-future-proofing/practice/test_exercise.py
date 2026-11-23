"""Chapter 13: the prompt contract. First docstring lines are what `make exercise` lists."""

import json
from pathlib import Path

import pytest

from lantern import case

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
SOURCE = "\n\n".join(case.read(f"invoices/{n}.txt") for n in ("NW-0388", "GTS-1182", "NW-0402"))
GOOD = json.dumps([{"invoice_id": "NW-0388", "total": 62500.0},
                   {"invoice_id": "NW-0402", "total": 71200}])


def body(name):
    return (PROMPTS / name).read_text(encoding="utf-8").split("---", 2)[2].strip()


def test_render_fills_the_v2_template(impl):
    """v2 renders with its one variable, and the evidence lands inside the <invoices> tags."""
    out = impl.render(body("v2.md"), {"invoices": "INVOICE TEXT"})
    assert "<invoices>\nINVOICE TEXT\n</invoices>" in out, "fill {invoices} with the variable"


def test_render_refuses_a_model_specific_token(impl):
    """v1 starts with /no_think, a Qwen3 control token: render refuses it."""
    with pytest.raises(ValueError):
        impl.render(body("v1.md"), {"invoices": "x"})


def test_render_refuses_missing_and_unused_variables(impl):
    """A placeholder with no variable, or a variable with no placeholder, is an error."""
    with pytest.raises(ValueError):
        impl.render("Read {invoices} and {ledger}.", {"invoices": "x"})
    with pytest.raises(ValueError):
        impl.render("Read {invoices}.", {"invoices": "x", "invoice": "typo"})


def test_a_reply_that_meets_the_contract_has_no_problems(impl):
    """A JSON list of rows with exactly invoice_id and a numeric total passes."""
    assert impl.validate(GOOD, impl.CONTRACT, source=SOURCE) == []
    assert impl.validate("[]", impl.CONTRACT, source=SOURCE) == [], "an empty list is valid"


def test_prose_or_a_fence_is_rejected(impl):
    """v1-style prose, a ```json fence or a thinking block is one problem: not JSON."""
    for reply in ("- NW-0388: 62,500.00", f"```json\n{GOOD}\n```", f"<think>ok</think>{GOOD}"):
        problems = impl.validate(reply, impl.CONTRACT, source=SOURCE)
        assert len(problems) == 1 and "not JSON" in problems[0], (reply, problems)


def test_wrong_fields_and_types_are_rejected(impl):
    """A total written as a string, a boolean, or an extra field each break the contract."""
    for row in ({"invoice_id": "NW-0388", "total": "62,500.00"},
                {"invoice_id": "NW-0388", "total": True},
                {"invoice_id": "NW-0388", "total": 62500.0, "vendor": "Northwind"}):
        assert impl.validate(json.dumps([row]), impl.CONTRACT, source=SOURCE), row


def test_ids_must_match_the_pattern_and_be_in_the_material(impl):
    """An id in the wrong form, or one the material never mentions, is a problem."""
    bad = json.dumps([{"invoice_id": "Northwind Freight Ltd", "total": 1.0},
                      {"invoice_id": "NW-0999", "total": 1.0}])
    problems = impl.validate(bad, impl.CONTRACT, source=SOURCE)
    assert len(problems) == 2, f"one problem per bad id, got {problems}"


def test_a_repeated_id_is_a_problem(impl):
    """The same invoice twice is reported."""
    rep = json.dumps([{"invoice_id": "NW-0388", "total": 62500.0}] * 2)
    assert impl.validate(rep, impl.CONTRACT, source=SOURCE), "report NW-0388 appearing twice"

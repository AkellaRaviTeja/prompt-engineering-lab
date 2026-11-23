"""Chapter 08: extract() with a validation retry. Each test's first docstring line is what
`make exercise` shows."""

import json
from datetime import date

import pytest
from pydantic import BaseModel, Field

from lantern import case
from lantern.testing import Scripted, say


class Row(BaseModel):
    """A short invoice row, enough to test the mechanism."""

    invoice_id: str
    invoice_date: date
    total_kbd: float = Field(description="Total due as a plain number")
    vat_number: str | None


INVOICE = case.read("invoices/NW-0419.txt")
GOOD = json.dumps({"invoice_id": "NW-0419", "invoice_date": "2026-03-03", "total_kbd": 94000.0,
                   "vat_number": None})
BAD_TOTAL = json.dumps({"invoice_id": "NW-0419", "invoice_date": "2026-03-03",
                        "total_kbd": "94,000.00", "vat_number": None})


def test_first_request_is_constrained_by_the_schema(impl):
    """The first call sends the invoice with the model's JSON schema as format=, at T = 0."""
    model = Scripted([say(GOOD)])
    impl.extract(INVOICE, chat=model, model_cls=Row)
    req = model.requests[0]
    assert req.get("format") == Row.model_json_schema(), "pass model_cls's JSON schema as format="
    assert req.get("temperature") == 0, "extract at temperature 0"
    assert len(req["messages"]) == 1 and req["messages"][0]["role"] == "user"
    assert "NW-0419" in req["messages"][0]["content"], "the invoice text must be in the request"


def test_valid_reply_is_returned_typed_after_one_call(impl):
    """A valid first reply comes back as a validated record, attempt 1, with one call."""
    model = Scripted([say(GOOD)])
    row, attempts = impl.extract(INVOICE, chat=model, model_cls=Row)
    assert isinstance(row, Row), f"return a {Row.__name__} instance, got {type(row).__name__}"
    assert row.invoice_date == date(2026, 3, 3) and row.total_kbd == 94000.0, "fields are typed"
    assert attempts == 1 and model.calls == 1


def test_invalid_reply_is_retried_with_its_error(impl):
    """An invalid reply goes back as an assistant turn, followed by its validation error."""
    model = Scripted([say(BAD_TOTAL), say(GOOD)])
    row, attempts = impl.extract(INVOICE, chat=model, model_cls=Row)
    assert row is not None and attempts == 2 and model.calls == 2, (row, attempts)
    second = model.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"], (
        "the retry is the first request, then the failed reply, then the error"
    )
    assert second[1]["content"] == BAD_TOTAL, "show the model exactly what it wrote"
    assert "total_kbd" in second[2]["content"], "the error message must name the failing field"


def test_text_that_is_not_json_is_retried_not_a_crash(impl):
    """A reply that is not JSON at all is treated as a validation failure and retried."""
    model = Scripted([say("Here is the extracted invoice data in JSON format:"), say(GOOD)])
    row, attempts = impl.extract(INVOICE, chat=model, model_cls=Row)
    assert row is not None and attempts == 2, "catch the failure and retry"


def test_gives_up_after_max_attempts(impl):
    """Still invalid after max_attempts: (None, max_attempts), and no extra calls."""
    model = Scripted([say(BAD_TOTAL) for _ in range(3)])
    row, attempts = impl.extract(INVOICE, chat=model, model_cls=Row, max_attempts=3)
    assert row is None and attempts == 3, f"got {(row, attempts)}"
    assert model.calls == 3, f"the cap is 3 calls, the model was called {model.calls} times"


def test_conversation_grows_with_each_retry(impl):
    """Each retry keeps every earlier failure and error in the conversation."""
    model = Scripted([say(BAD_TOTAL), say("not json"), say(GOOD)])
    row, attempts = impl.extract(INVOICE, chat=model, model_cls=Row, max_attempts=3)
    sizes = [len(r["messages"]) for r in model.requests]
    assert sizes == [1, 3, 5], f"messages sent per attempt were {sizes}"
    assert row is not None and attempts == 3


def test_zero_attempts_is_refused(impl):
    """max_attempts below 1 raises ValueError before any call."""
    model = Scripted([say(GOOD)])
    with pytest.raises(ValueError):
        impl.extract(INVOICE, chat=model, model_cls=Row, max_attempts=0)
    assert model.calls == 0

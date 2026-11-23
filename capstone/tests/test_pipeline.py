"""The pipeline: schema sent to the model, validation retry with the error, a cap, the version."""

from __future__ import annotations

import json
from typing import Literal

import pytest
from pydantic import BaseModel

from lantern.testing import Scripted, say

SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": ["threat", "logistics", "personal"]}},
    "required": ["label"],
}


class Label(BaseModel):
    label: Literal["threat", "logistics", "personal"]


@pytest.fixture
def prompt(prompts, tmp_path):
    folder = tmp_path / "sort"
    folder.mkdir()
    (folder / "v3.yaml").write_text(json.dumps({
        "name": "sort", "version": "v3", "system": "Sort messages.",
        "user": "{{sender}}: {{text}}", "schema": SCHEMA,
        "settings": {"temperature": 0, "max_tokens": 50},
    }), encoding="utf-8")
    return prompts.load_prompt("sort", "v3", root=tmp_path)


MSG = {"sender": "unknown +88 301", "text": "Some questions are expensive."}


def test_schema_and_settings_go_to_the_model(pipeline, prompt):
    """run() calls the model with the schema as `format` and the prompt's settings."""
    model = Scripted([say('{"label": "threat"}')])
    result = pipeline.run(prompt, MSG, Label, chat=model)
    req = model.requests[0]
    assert req.get("format") == SCHEMA, f"format must be the schema, got {req.get('format')}"
    assert req.get("temperature") == 0, "the prompt's settings are passed to the model"
    assert req.get("max_tokens") == 50, "the prompt's settings are passed to the model"
    assert req["messages"][-1]["content"] == "unknown +88 301: Some questions are expensive.", (
        "the rendered prompt is what the model receives"
    )
    assert result.value == Label(label="threat"), f"validated value, got {result.value!r}"
    assert result.attempts == 1, f"one call when the first reply is valid, got {result.attempts}"


def test_retry_shows_the_model_its_error(pipeline, prompt):
    """An invalid reply is retried with the bad reply and the validation error in the messages."""
    model = Scripted([say('{"label": "urgent"}'), say('{"label": "threat"}')])
    result = pipeline.run(prompt, MSG, Label, chat=model)
    assert model.calls == 2, f"one retry, got {model.calls} calls"
    first, second = model.requests[0]["messages"], model.requests[1]["messages"]
    assert second[: len(first)] == first, "the retry keeps the original conversation"
    assert second[len(first)] == {"role": "assistant", "content": '{"label": "urgent"}'}, (
        "the retry shows the model its own invalid reply"
    )
    feedback = second[-1]
    assert feedback["role"] == "user", "the error goes back as a user turn"
    assert "label" in feedback["content"] and "urgent" in feedback["content"], (
        f"the feedback must carry the validation error, got {feedback['content']!r}"
    )
    assert result.value == Label(label="threat"), "the second, valid reply is the result"
    assert result.attempts == 2, f"attempts counts every call, got {result.attempts}"
    assert len(result.errors) == 1, f"one error recorded, got {result.errors}"


def test_prose_reply_is_retried(pipeline, prompt):
    """A reply that is not JSON at all fails validation and is retried like any other."""
    model = Scripted([say("It is a threat."), say('{"label": "threat"}')])
    result = pipeline.run(prompt, MSG, Label, chat=model)
    assert model.calls == 2, f"prose must be retried, got {model.calls} calls"
    assert result.ok, "the valid second reply is accepted"


def test_attempts_are_capped(pipeline, prompt):
    """After max_attempts invalid replies the result is empty, with every error kept."""
    model = Scripted([say('{"label": "urgent"}')] * 5)
    result = pipeline.run(prompt, MSG, Label, chat=model, max_attempts=3)
    assert model.calls == 3, f"max_attempts=3 means 3 calls, got {model.calls}"
    assert result.value is None and not result.ok, "no valid reply means no value"
    assert result.attempts == 3, f"attempts {result.attempts}"
    assert len(result.errors) == 3, f"one error per failed attempt, got {len(result.errors)}"
    one = Scripted([say('{"label": "urgent"}')] * 2)
    pipeline.run(prompt, MSG, Label, chat=one, max_attempts=1)
    assert one.calls == 1, f"max_attempts=1 means no retry, got {one.calls} calls"


def test_version_logged_on_every_call(pipeline, prompt):
    """Every call, retries included, carries prompt_version=name@version for the call log."""
    model = Scripted([say("no"), say("{}"), say('{"label": "personal"}')])
    result = pipeline.run(prompt, MSG, Label, chat=model)
    versions = [r.get("prompt_version") for r in model.requests]
    assert versions == ["sort@v3"] * 3, f"every call must be labelled sort@v3, got {versions}"
    assert result.prompt_version == "sort@v3", f"the result names it too: {result.prompt_version}"


def test_failed_call_is_raised_not_hidden(pipeline, prompt):
    """A model call that fails (a timeout) is raised, never returned as an empty result."""
    model = Scripted([TimeoutError("Ollama did not answer")])
    with pytest.raises(TimeoutError):
        pipeline.run(prompt, MSG, Label, chat=model)


def test_extract_invoice(pipeline):
    """extract_invoice() uses extract-invoice@v1 and returns a validated Invoice."""
    reply = {"invoice_id": "NW-0419", "vendor": "Northwind Freight Ltd",
             "date": "2026-03-03", "total": 94000.0}
    model = Scripted([say(json.dumps(reply))])
    result = pipeline.extract_invoice("INVOICE NW-0419 ...", chat=model)
    req = model.requests[0]
    assert req.get("prompt_version") == "extract-invoice@v1", req.get("prompt_version")
    assert "INVOICE NW-0419 ..." in req["messages"][-1]["content"], "the invoice is in the prompt"
    assert isinstance(result.value, pipeline.Invoice), f"got {type(result.value)}"
    assert result.value.total == 94000.0, f"total {result.value.total}"
    assert result.value.model_dump(mode="json")["date"] == "2026-03-03", "date is a date"


def test_invoice_rules_beyond_the_schema(pipeline):
    """Invoice rejects what the schema lets through: a bad id, a bad date, a total of zero."""
    good = {"invoice_id": "NW-0419", "vendor": "Northwind", "date": "2026-03-03", "total": 1.0}
    pipeline.Invoice.model_validate(good)
    for bad in ({"invoice_id": "INVOICE NW-0419"}, {"date": "3 March 2026"}, {"total": 0}):
        with pytest.raises(ValueError):
            pipeline.Invoice.model_validate({**good, **bad})


def test_classify_message(pipeline):
    """classify_message() runs the version asked for and rejects a label outside the three."""
    model = Scripted([say('{"label": "urgent"}'), say('{"label": "logistics"}')])
    result = pipeline.classify_message(
        {"sender": "Gulf Tug dispatch", "text": "Two tugs confirmed."}, chat=model, version="v2")
    assert model.requests[0].get("prompt_version") == "classify-message@v2", (
        model.requests[0].get("prompt_version"))
    assert result.value == pipeline.MessageLabel(label="logistics"), f"got {result.value!r}"
    assert result.attempts == 2, "the invalid label was retried"

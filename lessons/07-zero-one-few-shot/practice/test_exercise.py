"""Chapter 07: a few-shot classifier. Each test's first docstring line is what `make exercise`
shows."""

import json

import pytest

from lantern import case
from lantern.testing import Scripted, say

LABELS = ["threat", "logistics", "personal"]
MESSAGES = case.jsonl("messages.jsonl")
BY_ID = {m["id"]: m for m in MESSAGES}
CLEAR = [BY_ID[i] for i in ("M01", "M02", "M03", "M04", "M05", "M12")]  # file order


def answer(label, prompt=100):
    return say(json.dumps({"label": label}), prompt=prompt)


def test_schema_allows_only_the_labels(impl):
    """The schema is one object with one required field, label, limited to the labels."""
    s = impl.label_schema(LABELS)
    assert s["type"] == "object" and s["required"] == ["label"], s
    assert s["properties"]["label"]["enum"] == LABELS, "the label must be an enum of the labels"


def test_examples_are_chosen_per_label_and_interleaved(impl):
    """Two clear examples per label come back interleaved: threat, logistics, personal, ..."""
    ids = [m["id"] for m in impl.choose_examples(CLEAR, LABELS, per_label=2)]
    assert ids == ["M03", "M02", "M01", "M12", "M04", "M05"], (
        f"got {ids}: take each label's first two in pool order, then interleave by label"
    )
    one = [m["label"] for m in impl.choose_examples(MESSAGES, LABELS, per_label=1)]
    assert one == LABELS, f"one per label should give {LABELS}, got {one}"


def test_a_label_short_of_examples_is_refused(impl):
    """A pool without enough examples of a label raises ValueError."""
    with pytest.raises(ValueError):
        impl.choose_examples(CLEAR, LABELS, per_label=3)


def test_request_has_system_examples_schema_and_message(impl):
    """classify sends the system prompt, example turns in JSON, the message, and the schema."""
    model = Scripted([answer("threat")])
    ex = [BY_ID["M03"], BY_ID["M02"]]
    impl.classify(BY_ID["M07"], chat=model, system="TASK", examples=ex, labels=LABELS)
    req = model.requests[0]
    turns = req["messages"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant", "user"], (
        "each example is a user turn then an assistant turn; the message is the last user turn"
    )
    assert json.loads(turns[1]["content"]) == {"label": "threat"}, (
        "example answers must be in the schema's JSON shape"
    )
    assert "M07" not in turns[-1]["content"] and BY_ID["M07"]["text"] in turns[-1]["content"]
    assert req.get("system") == "TASK", "pass the task as system="
    assert req.get("format") == impl.label_schema(LABELS), "constrain the answer with format="
    assert req.get("temperature") == 0, "classify at temperature 0"


def test_label_is_read_from_the_json_reply(impl):
    """A reply {"label": "logistics"} gives logistics, with the call's prompt tokens."""
    model = Scripted([answer("logistics", prompt=321)])
    label, tokens = impl.classify(BY_ID["M06"], chat=model, system="T", examples=[],
                                  labels=LABELS)
    assert (label, tokens) == ("logistics", 321), f"got {(label, tokens)}"


def test_bad_replies_are_invalid_not_a_crash(impl):
    """A reply that is not JSON, or a label outside the list, is 'invalid'."""
    for text in ("threat.", json.dumps({"label": "urgent"}), json.dumps(["threat"])):
        label, _ = impl.classify(BY_ID["M06"], chat=Scripted([say(text)]), system="T",
                                 examples=[], labels=LABELS)
        assert label == "invalid", f"{text!r} should be invalid, got {label!r}"


def test_score_measures_agreement_with_gold(impl):
    """score returns predictions, accuracy against gold labels, counts and total tokens."""
    items = [BY_ID["M06"], BY_ID["M07"], BY_ID["M09"], BY_ID["M10"]]  # logistics threat pers log
    model = Scripted([answer("logistics", 50), answer("threat", 50), answer("threat", 50),
                      say("no idea", prompt=50)])
    out = impl.score(items, chat=model, system="T", examples=[], labels=LABELS)
    assert out["preds"] == ["logistics", "threat", "threat", "invalid"], out["preds"]
    assert out["accuracy"] == 0.5, f"2 of 4 match the gold labels, got {out['accuracy']}"
    assert out["counts"] == {"logistics": 1, "threat": 2, "invalid": 1}, out["counts"]
    assert out["prompt_tokens"] == 200, "add up every call's prompt tokens"


def test_every_call_carries_the_same_examples(impl):
    """Every message is classified with the same examples in front of it."""
    ex = impl.choose_examples(CLEAR, LABELS, per_label=1)
    items = [BY_ID["M06"], BY_ID["M09"]]
    model = Scripted([answer("logistics"), answer("personal")])
    impl.score(items, chat=model, system="T", examples=ex, labels=LABELS)
    a, b = (r["messages"] for r in model.requests)
    assert a[:-1] == b[:-1] and len(a) == 2 * len(ex) + 1, "examples, then one message, each call"

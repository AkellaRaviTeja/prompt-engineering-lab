"""Chapter 07 exercise: write the few-shot classifier.

Four pieces: a schema that allows only the three labels, examples chosen per label and
interleaved, the examples as earlier chat turns, and a scorer that measures agreement with the
gold labels. Grade it with `make exercise N=07` (offline: the tests use a scripted model). When
every test passes, run the lesson on your classifier: `make lesson N=07 ARGS=--mine`.

Stuck? `make hint N=07`. Start again? `make exercise-reset N=07`.

A message is a dict like {"id": "M03", "from": "unknown +88 301", "text": "...",
"label": "threat"}, as in case/messages.jsonl.
"""

from __future__ import annotations

import json  # noqa: F401  (the solution uses it)
from collections import Counter  # noqa: F401
from collections.abc import Callable
from typing import Any


def ask(m: dict) -> str:
    """The user turn for one message (the same wording the lesson uses). Already written."""
    return f"Message from {m['from']}: \"{m['text']}\""


def label_schema(labels: list[str]) -> dict[str, Any]:
    """A JSON schema for one object with one field, `label`, that must be one of `labels`.

    Passed as chat(format=...), Ollama turns it into a grammar and a hosted provider enforces it
    natively, so the reply can only be {"label": "<one of labels>"}.
    """
    # TODO 1: an "object" schema with one required property "label": a string with an "enum".
    raise NotImplementedError("TODO 1: the label schema")


def choose_examples(pool: list[dict], labels: list[str], per_label: int) -> list[dict]:
    """The first `per_label` messages of each label in `pool`, interleaved label by label.

    With labels [threat, logistics, personal] and per_label=2 the result is: the first threat,
    the first logistics, the first personal, the second threat, ... so no label's examples sit
    together at the end (recency pulls toward the last examples). Raise ValueError if the pool
    has fewer than `per_label` messages of any label.
    """
    # TODO 2: for each label, the first per_label messages with that label, in pool order.
    # TODO 3: refuse a label that is short of examples.
    # TODO 4: interleave: round i takes the i-th example of every label, in label order.
    raise NotImplementedError("TODO 2 to 4: choosing examples")


def example_turns(examples: list[dict]) -> list[dict]:
    """Each example as a user turn (ask(m)) and the assistant's answer, in the schema's shape.

    The assistant content is the JSON the schema allows, for example '{"label": "threat"}', so
    the examples show the model the exact format it must answer in.
    """
    # TODO 5: two turns per example, user then assistant.
    raise NotImplementedError("TODO 5: examples as turns")


def classify(
    message: dict, *, chat: Callable[..., Any], system: str, examples: list[dict],
    labels: list[str],
) -> tuple[str, int]:
    """One message's label (or "invalid"), and the prompt tokens the call used.

    Call chat(turns, system=system, format=label_schema(labels), temperature=0, max_tokens=20)
    where turns are the example turns and then ask(message) as the last user turn. The reply's
    .text should be JSON; .prompt_tokens is what the call cost.
    """
    # TODO 6: build the turns and call the model with the schema, at temperature 0.
    # TODO 7: read the label from the JSON reply. A reply that is not JSON, or a label not in
    #         `labels`, is "invalid": never crash on a bad reply.
    raise NotImplementedError("TODO 6 and 7: one classification")


def score(
    items: list[dict], *, chat: Callable[..., Any], system: str, examples: list[dict],
    labels: list[str],
) -> dict[str, Any]:
    """Classify every item and score the labels against each item's gold `label`.

    Return a dict:
        preds          the predicted label for each item, in order ("invalid" included)
        accuracy       the share of items whose prediction equals their gold label
        counts         {label: how many items got it}, "invalid" included when it occurs
        prompt_tokens  the prompt tokens of every call, added up
    """
    # TODO 8: classify each item with the same system prompt and examples.
    # TODO 9: accuracy against m["label"], the counts, and the tokens.
    raise NotImplementedError("TODO 8 and 9: scoring")

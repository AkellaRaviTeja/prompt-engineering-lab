"""Chapter 07 reference solution: a few-shot classifier. Compare it with yours after trying."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from typing import Any


def ask(m: dict) -> str:
    """The user turn for one message (the same wording the lesson uses)."""
    return f"Message from {m['from']}: \"{m['text']}\""


def label_schema(labels: list[str]) -> dict[str, Any]:
    """A JSON schema for one object with one field, `label`, that must be one of `labels`."""
    return {
        "type": "object",
        "properties": {"label": {"type": "string", "enum": list(labels)}},
        "required": ["label"],
    }


def choose_examples(pool: list[dict], labels: list[str], per_label: int) -> list[dict]:
    """The first `per_label` messages of each label in `pool`, interleaved label by label."""
    by_label = {lab: [m for m in pool if m["label"] == lab][:per_label] for lab in labels}
    short = [lab for lab, ms in by_label.items() if len(ms) < per_label]
    if short:
        raise ValueError(f"not enough examples for {short} in the pool")
    return [by_label[lab][i] for i in range(per_label) for lab in labels]


def example_turns(examples: list[dict]) -> list[dict]:
    """Each example as a user turn and the assistant's answer, in the schema's JSON shape."""
    turns: list[dict] = []
    for m in examples:
        turns += [
            {"role": "user", "content": ask(m)},
            {"role": "assistant", "content": json.dumps({"label": m["label"]})},
        ]
    return turns


def classify(
    message: dict, *, chat: Callable[..., Any], system: str, examples: list[dict],
    labels: list[str],
) -> tuple[str, int]:
    """One message's label (or "invalid"), and the prompt tokens the call used."""
    r = chat(
        [*example_turns(examples), {"role": "user", "content": ask(message)}],
        system=system, format=label_schema(labels), temperature=0, max_tokens=20,
    )
    try:
        label = json.loads(r.text).get("label")
    except (ValueError, AttributeError):
        label = None
    return (label if label in labels else "invalid"), r.prompt_tokens


def score(
    items: list[dict], *, chat: Callable[..., Any], system: str, examples: list[dict],
    labels: list[str],
) -> dict[str, Any]:
    """Classify every item and score the labels against each item's gold `label`."""
    preds, tokens = [], 0
    for m in items:
        label, used = classify(m, chat=chat, system=system, examples=examples, labels=labels)
        preds.append(label)
        tokens += used
    correct = sum(p == m["label"] for p, m in zip(preds, items, strict=True))
    return {
        "preds": preds,
        "accuracy": correct / len(items) if items else 0.0,
        "counts": dict(Counter(preds)),
        "prompt_tokens": tokens,
    }

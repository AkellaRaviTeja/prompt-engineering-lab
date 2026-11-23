"""Chapter 13 solution: the prompt contract. Read it once you have tried."""

from __future__ import annotations

import json
import re
import string
from typing import Any

# Tokens that only one model family understands. In any other model they are just words.
MODEL_SPECIFIC = ("/no_think", "/think", "<|im_start|>", "<|im_end|>", "[INST]")

CONTRACT = {
    "fields": {"invoice_id": "string", "total": "number"},
    "id_field": "invoice_id",
    "id_pattern": r"^[A-Z]{2,4}-\d{4}$",
}


def render(template: str, variables: dict[str, str]) -> str:
    """Fill a prompt template's {placeholders} from `variables`.

    Raises ValueError when the template holds a model-specific token (MODEL_SPECIFIC), when a
    placeholder has no variable, or when a variable has no placeholder (a typo that would
    silently drop evidence).
    """
    for token in MODEL_SPECIFIC:
        if token in template:
            raise ValueError(f"model-specific token {token!r} in the template")
    names = {field for _, field, _, _ in string.Formatter().parse(template) if field}
    missing, unused = names - set(variables), set(variables) - names
    if missing or unused:
        raise ValueError(f"missing variables {sorted(missing)}, unused {sorted(unused)}")
    return template.format(**variables)


def validate(reply: str, contract: dict[str, Any], *, source: str) -> list[str]:
    """Everything wrong with a reply under the contract, one string each. [] means it meets it.

    The reply must be a JSON list and nothing else: no prose, no code fence, no thinking block.
    Each row must have exactly the contract's fields, each of its type ("string" or "number";
    a boolean is not a number). The id field must match id_pattern and appear in `source`, the
    material the model was given, and no id may appear twice.
    """
    try:
        data = json.loads(reply)
    except ValueError:
        return ["not JSON: prose, a code fence or a thinking block around the data"]
    if not isinstance(data, list):
        return ["not a JSON list"]
    kinds = {"string": str, "number": (int, float)}
    problems: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(data):
        if not isinstance(row, dict) or set(row) != set(contract["fields"]):
            problems.append(f"row {i}: fields must be exactly {sorted(contract['fields'])}")
            continue
        for name, kind in contract["fields"].items():
            if isinstance(row[name], bool) or not isinstance(row[name], kinds[kind]):
                problems.append(f"row {i}: {name} must be a {kind}")
        rid = str(row[contract["id_field"]])
        if not re.match(contract["id_pattern"], rid):
            problems.append(f"row {i}: {rid!r} does not match {contract['id_pattern']}")
        elif rid not in source:
            problems.append(f"row {i}: {rid} is not in the material")
        if rid in seen:
            problems.append(f"row {i}: {rid} appears twice")
        seen.add(rid)
    return problems

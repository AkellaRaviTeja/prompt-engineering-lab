"""Chapter 13 exercise: the prompt contract.

A prompt that survives a model swap is a template plus a contract. The template is filled by
code, and refuses anything only one model family understands. The reply is checked by code
against the contract, so a reply that only one model's habits made readable (prose a regex
happened to match, a fenced block, a thinking block) is rejected, whichever model sent it.

Grade it with `make exercise N=13` (offline, no model). Stuck? `make hint N=13`.
Start again? `make exercise-reset N=13`.
"""

from __future__ import annotations

import json  # noqa: F401  (the solution uses these)
import re  # noqa: F401
import string  # noqa: F401
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
    # TODO 1: refuse any MODEL_SPECIFIC token found in the template.
    # TODO 2: the placeholder names: string.Formatter().parse(template) yields
    #         (literal, field_name, spec, conversion); field_name is None for plain text.
    # TODO 3: refuse missing and unused variables, then fill the template.
    raise NotImplementedError("TODO 1 to 3: render")


def validate(reply: str, contract: dict[str, Any], *, source: str) -> list[str]:
    """Everything wrong with a reply under the contract, one string each. [] means it meets it.

    The reply must be a JSON list and nothing else: no prose, no code fence, no thinking block.
    Each row must have exactly the contract's fields, each of its type ("string" or "number";
    a boolean is not a number). The id field must match id_pattern and appear in `source`, the
    material the model was given, and no id may appear twice.
    """
    # TODO 4: json.loads the whole reply. Not JSON, or not a list: one problem, and stop.
    # TODO 5: per row: exactly the contract's fields; each field of its type.
    # TODO 6: per row: the id matches id_pattern, appears in source, and is not a repeat.
    raise NotImplementedError("TODO 4 to 6: validate")

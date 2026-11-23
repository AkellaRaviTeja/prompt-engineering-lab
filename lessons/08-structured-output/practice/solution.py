"""Chapter 08 reference solution: schema-constrained extraction with a validation retry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError


def extract(
    text: str,
    *,
    chat: Callable[..., Any],
    model_cls: type[BaseModel],
    max_attempts: int = 3,
) -> tuple[BaseModel | None, int]:
    """Extract one record from `text`, validated by `model_cls`, retrying with the error."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    schema = model_cls.model_json_schema()
    messages = [{"role": "user", "content": f"Extract this invoice.\n\n{text}"}]
    for attempt in range(1, max_attempts + 1):
        r = chat(messages, format=schema, temperature=0, max_tokens=400)
        try:
            return model_cls.model_validate_json(r.text), attempt
        except ValidationError as e:
            messages = [
                *messages,
                {"role": "assistant", "content": r.text},
                {"role": "user", "content": f"That failed validation: {e}. Fix it."},
            ]
    return None, max_attempts

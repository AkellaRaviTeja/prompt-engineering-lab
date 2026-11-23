"""Chapter 08 exercise: write extract(), the path everything after this chapter trusts.

A schema-constrained call, Pydantic validation, and a retry that shows the model its own
validation error, with a cap. The eval suite (evals/providers/lantern_provider.py) makes the
same schema-constrained call. Grade it with `make exercise N=08` (offline: the tests use a
scripted model). When every test passes, run the lesson on your extract():
`make lesson N=08 ARGS=--mine`.

Stuck? `make hint N=08`. Start again? `make exercise-reset N=08`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError  # noqa: F401  (the solution uses both)


def extract(
    text: str,
    *,
    chat: Callable[..., Any],
    model_cls: type[BaseModel],
    max_attempts: int = 3,
) -> tuple[BaseModel | None, int]:
    """Extract one record from `text`, validated by `model_cls`, retrying with the error.

    Each attempt calls
        chat(messages, format=<model_cls's JSON schema>, temperature=0, max_tokens=400)
    which returns a reply with `.text`. The first request is one user turn:
        "Extract this invoice.\\n\\n" + text

    If the reply validates (model_cls.model_validate_json), return (the record, attempt number).
    If not, the next request is the whole conversation so far plus the failed reply as an
    assistant turn and a user turn that quotes the validation error and asks for a fix. After
    `max_attempts` failures return (None, max_attempts): a person looks at it. Raise ValueError
    if max_attempts < 1.
    """
    # TODO 1: refuse max_attempts < 1.
    # TODO 2: the schema is model_cls.model_json_schema(); the first request is one user turn.
    # TODO 3: for each attempt: call the model with format=schema at temperature 0, and try to
    #         validate the reply. Text that is not JSON at all is a ValidationError too.
    # TODO 4: on ValidationError, append the failed reply (assistant) and a user turn that
    #         contains str(error), then try again.
    # TODO 5: out of attempts: return (None, max_attempts).
    raise NotImplementedError("TODO 1 to 5: extract with a validation retry")

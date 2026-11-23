"""The pipeline: load a prompt version, render it, call the model with the schema, validate.

When the reply fails validation, the model sees its own reply and the validation error, and
tries again, up to a cap. Every call is logged with the prompt version. A failed model call
(a timeout, a refused connection) is not a validation failure: it is raised, never turned into
an empty result.

    result = extract_invoice(text)            # the real model through lantern.chat
    result = extract_invoice(text, chat=fake) # any function shaped like lantern.chat
    result.value, result.attempts, result.errors
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from prompts import Prompt, load_prompt
from pydantic import BaseModel, Field, ValidationError

from lantern import chat as lantern_chat

RETRY = (
    "Your reply failed validation:\n\n{error}\n\n"
    "Reply again with the corrected JSON object only."
)


class Invoice(BaseModel):
    """One supplier invoice, as the link chart needs it."""

    invoice_id: str = Field(pattern=r"^[A-Z]{2,4}-\d{4}$")
    vendor: str = Field(min_length=1)
    date: dt.date
    total: float = Field(gt=0)


class MessageLabel(BaseModel):
    """One message from Reyes's work phone, sorted."""

    label: Literal["threat", "logistics", "personal"]


TASKS: dict[str, type[BaseModel]] = {
    "extract-invoice": Invoice,
    "classify-message": MessageLabel,
}


@dataclass
class Result:
    value: BaseModel | None  # the validated object, or None when every attempt failed
    attempts: int
    errors: list[str] = field(default_factory=list)  # one validation error per failed attempt
    prompt_version: str = ""
    text: str = ""  # the last reply as the model wrote it

    @property
    def ok(self) -> bool:
        return self.value is not None


def run(
    prompt: Prompt,
    fields: dict[str, Any],
    model: type[BaseModel],
    *,
    chat: Callable[..., Any] | None = None,
    max_attempts: int = 3,
) -> Result:
    """Render `prompt` with `fields`, call the model, validate against `model`, retry on error."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    call = chat or lantern_chat
    messages = prompt.render(**fields)
    errors: list[str] = []
    text = ""
    for attempt in range(1, max_attempts + 1):
        reply = call(messages, format=prompt.schema, prompt_version=prompt.id, **prompt.settings)
        text = reply.text
        try:
            value = model.model_validate_json(text)
        except ValidationError as e:
            errors.append(str(e))
            messages = [
                *messages,
                {"role": "assistant", "content": text},
                {"role": "user", "content": RETRY.format(error=e)},
            ]
            continue
        return Result(value, attempt, errors, prompt.id, text)
    return Result(None, max_attempts, errors, prompt.id, text)


def run_task(
    task: str,
    version: str,
    fields: dict[str, Any],
    *,
    chat: Callable[..., Any] | None = None,
    max_attempts: int = 3,
) -> Result:
    """Run one of the pipeline's tasks (extract-invoice, classify-message) at a prompt version."""
    if task not in TASKS:
        raise LookupError(f"unknown task {task!r}; tasks: {', '.join(TASKS)}")
    prompt = load_prompt(task, version)
    return run(prompt, fields, TASKS[task], chat=chat, max_attempts=max_attempts)


def extract_invoice(
    text: str, *, chat: Callable[..., Any] | None = None, version: str = "v1",
    max_attempts: int = 3,
) -> Result:
    """Extract one invoice's fields from its text."""
    return run_task("extract-invoice", version, {"invoice": text}, chat=chat,
                    max_attempts=max_attempts)


def classify_message(
    message: dict[str, str], *, chat: Callable[..., Any] | None = None, version: str = "v1",
    max_attempts: int = 3,
) -> Result:
    """Sort one message ({"sender", "text"}) into threat, logistics or personal."""
    fields = {"sender": message["sender"], "text": message["text"]}
    return run_task("classify-message", version, fields, chat=chat, max_attempts=max_attempts)

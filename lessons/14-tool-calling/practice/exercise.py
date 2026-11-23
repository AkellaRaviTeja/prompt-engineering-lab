"""Chapter 14 exercise: write the tool loop, with argument validation and a step cap.

Fill in `validate` and `run_tools`. Grade them with `make exercise N=14` (offline: the tests use
a scripted model). When every test passes, run the live lesson on your loop:
`make lesson N=14 ARGS=--mine`.

Stuck? `make hint N=14`. Start again? `make exercise-reset N=14`.
"""

from __future__ import annotations

import json  # noqa: F401  (the solution uses these)
import re  # noqa: F401
from collections.abc import Callable
from typing import Any

TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
         "object": dict, "array": list}


def validate(arguments: Any, schema: dict[str, Any]) -> list[str]:
    """What is wrong with a call's arguments against its JSON schema. [] means valid.

    Check, in this order: the arguments are a dict; every name in `required` is present; no
    argument outside `properties` when `additionalProperties` is False; each value has its
    `type` (true is not a number); a value is in its `enum`; a string matches its `pattern`
    (`re.search`). Return one plain-English message per problem.
    """
    # TODO 1: not a dict -> ["arguments must be a JSON object"]
    # TODO 2: a message for every missing required argument
    # TODO 3: for each argument: unknown name, wrong type, not in enum, pattern does not match
    raise NotImplementedError("TODO 1 to 3: validate the arguments against the schema")


def run_tools(
    question: str,
    *,
    chat: Callable[..., Any],
    tools: list[dict],
    functions: dict[str, Callable[..., Any]],
    system: str | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """Answer a question with tools: call, validate, run, return results, until an answer.

    `tools` are {"name", "description", "parameters"} dicts. `chat(messages, tools=tools)`
    returns a reply with `.text` and `.tool_calls` (each with `.name`, `.arguments`, `.id`).

    Return a dict:
        answer          the model's text answer, or None if the step cap was reached
        turns           how many times the model was called
        calls           one {"name", "arguments", "valid"} per requested call, in order
        parallel        how many replies carried more than one call
        parse_failures  0 (the API parses calls for you; the hand-built version counts these)
        stopped         "answered" or "max_steps"
    """
    # TODO 4: the conversation starts with the system prompt (if any), then the question.
    messages: list[dict[str, Any]] = []  # noqa: F841

    for turn in range(1, max_steps + 1):  # noqa: B007
        # TODO 5: call the model with the conversation and the tools. No tool calls: return.

        # TODO 6: give every call an id (c.id, or make one up), and append ONE assistant turn
        #         with "content" and "tool_calls": [{"id", "function": {"name", "arguments"}}].

        # TODO 7: for each call, in order: an unknown tool or arguments that fail validate()
        #         become {"error": ...} and the function is NOT called; a LookupError from the
        #         function becomes {"error": str(e)}. Append {"role": "tool", "tool_call_id",
        #         "tool_name", "content": json.dumps(result)} for every call.
        raise NotImplementedError("TODO 5 to 7: the body of the loop")

    # TODO 8: the step cap was reached without an answer.
    raise NotImplementedError("TODO 8: what to return when max_steps is reached")

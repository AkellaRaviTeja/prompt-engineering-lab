"""Chapter 14 reference solution: the tool loop. Compare it with yours after you have tried."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
         "object": dict, "array": list}


def validate(arguments: Any, schema: dict[str, Any]) -> list[str]:
    """What is wrong with a call's arguments against its JSON schema. [] means valid."""
    if not isinstance(arguments, dict):
        return ["arguments must be a JSON object"]
    errors = []
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in arguments:
            errors.append(f"missing required argument {name!r}")
    for name, value in arguments.items():
        spec = props.get(name)
        if spec is None:
            if schema.get("additionalProperties") is False:
                errors.append(f"unexpected argument {name!r}")
            continue
        want = spec.get("type")
        # bool is an int in Python, but true is not a number in JSON
        if want and not (isinstance(value, TYPES[want])
                         and (want == "boolean" or not isinstance(value, bool))):
            errors.append(f"{name!r} must be a {want}, got {type(value).__name__}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{name!r} must be one of {spec['enum']}")
        if "pattern" in spec and not re.search(spec["pattern"], value):
            errors.append(f"{name!r} does not match {spec['pattern']}")
    return errors


def run_tools(
    question: str,
    *,
    chat: Callable[..., Any],
    tools: list[dict],
    functions: dict[str, Callable[..., Any]],
    system: str | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """Answer a question with tools: call, validate, run, return results, until an answer."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})
    schemas = {t["name"]: t["parameters"] for t in tools}
    calls: list[dict[str, Any]] = []
    parallel = 0

    for turn in range(1, max_steps + 1):
        r = chat(messages, tools=tools)
        if not r.tool_calls:
            return {"answer": r.text, "turns": turn, "calls": calls, "parallel": parallel,
                    "parse_failures": 0, "stopped": "answered"}
        parallel += len(r.tool_calls) > 1
        ids = [c.id or f"call_{turn}_{i}" for i, c in enumerate(r.tool_calls)]
        messages.append({
            "role": "assistant",
            "content": r.text,
            "tool_calls": [{"id": i, "function": {"name": c.name, "arguments": c.arguments}}
                           for i, c in zip(ids, r.tool_calls, strict=True)],
        })
        for call_id, c in zip(ids, r.tool_calls, strict=True):
            if c.name not in functions:
                result: Any = {"error": f"no tool named {c.name!r}"}
                valid = False
            elif problems := validate(c.arguments, schemas[c.name]):
                result = {"error": "invalid arguments: " + "; ".join(problems)}
                valid = False
            else:
                valid = True
                try:
                    result = functions[c.name](**c.arguments)
                except LookupError as e:  # "not found" is an answer the model must see
                    result = {"error": str(e)}
            calls.append({"name": c.name, "arguments": c.arguments, "valid": valid})
            messages.append({"role": "tool", "tool_call_id": call_id, "tool_name": c.name,
                             "content": json.dumps(result)})

    return {"answer": None, "turns": max_steps, "calls": calls, "parallel": parallel,
            "parse_failures": 0, "stopped": "max_steps"}

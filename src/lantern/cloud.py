"""The hosted tier: Anthropic, OpenAI and Gemini, each through its own native features.

Install with `uv sync --extra cloud` and set the provider's key in .env. Only synthetic material
goes to these: in the story evidence never leaves LANTERN, and every case document in this lab
is fictional.

Nothing here imitates a feature with a prompt. Structured output uses the provider's schema
enforcement, tools use its native tool calling, `cache=True` uses its prompt cache, and `think`
uses its reasoning setting. A setting the provider cannot take (Claude has no `seed` and no
log-probabilities; current Claude models reject sampling settings) is not sent, and is reported:
once per run on the console, and on every reply in `Reply.unsupported`.

Each adapter is split in two so it can be tested without a key or the network:
`<provider>_request(...)` builds the exact keyword arguments for the SDK call, and
`<provider>_reply(...)` reads the SDK's response object into a Reply.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any

from lantern import retry
from lantern.config import load_config
from lantern.llm import Message, Reply, ToolCall

_warned: set[tuple[str, str]] = set()


def report_unsupported(provider: str, model: str, names: list[str]) -> None:
    """Say once per run which settings a provider did not take."""
    for n in names:
        if (provider, n) not in _warned:
            _warned.add((provider, n))
            print(f"[hosted] {provider} {model}: `{n}` is not supported, not sent", file=sys.stderr)


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """A JSON schema in the strict form provider schema enforcement accepts.

    Every object gets `additionalProperties: false` and lists every property as required
    (optional fields are already nullable in a Pydantic schema), `$defs` references are kept,
    and keys strict mode rejects (`title`, `default`, `format` on strings) are dropped.
    """
    s = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k in ("title", "default"):
                node.pop(k, None)
            if node.get("type") == "string":
                node.pop("format", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)
    return s


def _split(messages: list[Message]) -> tuple[str, list[Message]]:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    return system, [m for m in messages if m["role"] != "system"]


def chat(
    provider: str,
    messages: list[Message],
    model: str,
    s: dict[str, Any],
    format: dict[str, Any] | str | None,
    tools: list[dict[str, Any]] | None,
    timeout: float,
) -> Reply:
    if os.getenv("LANTERN_REPLAY"):
        from lantern import recording

        return recording.replay(provider, messages, model, s, format, tools)
    adapters = {"anthropic": _anthropic, "openai": _openai, "gemini": _gemini}
    if provider not in adapters:
        raise SystemExit(f"Unknown provider {provider!r}. Use anthropic, openai or gemini.")
    reply = adapters[provider](messages, model, s, format, tools, timeout)
    report_unsupported(provider, model, reply.unsupported)
    if os.getenv("LANTERN_RECORD"):
        from lantern import recording

        recording.save(provider, messages, model, s, format, tools, reply)
    return reply


def _key(name: str) -> str:
    key = os.environ.get(name)
    if not key:
        raise SystemExit(
            f"TIER=hosted needs {name} in .env (see .env.example). Without a key, the chapter "
            "checks read the committed recorded run: make challenge N=NN TIER=hosted"
        )
    return key


# ---- Anthropic --------------------------------------------------------------------------------


def anthropic_request(
    messages: list[Message],
    model: str,
    s: dict[str, Any],
    format: dict[str, Any] | str | None,
    tools: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], list[str]]:
    """The keyword arguments for `client.messages.create`, and the settings left out."""
    system, turns = _split(messages)
    unsupported: list[str] = []
    kw: dict[str, Any] = {"model": model, "max_tokens": s["max_tokens"], "messages": turns}
    if system:
        kw["system"] = system
    # Current Claude models reject sampling settings (temperature, top_p, top_k): a 400.
    unsupported += ["temperature", "top_k", "top_p"]
    unsupported.append("seed")  # Claude has no seed
    if s.get("logprobs"):
        unsupported.append("logprobs")  # nor log-probabilities
    off = load_config()["hosted"]["anthropic"].get("thinking_off", {})
    if s["think"]:
        kw["thinking"] = {"type": "adaptive", "display": "summarized"}
    elif off.get(model, "disabled"):
        kw["thinking"] = {"type": off.get(model, "disabled")}
    else:
        unsupported.append("think=False")  # this model cannot turn thinking off
    if format is not None:
        schema = format if isinstance(format, dict) else {"type": "object"}
        kw["output_config"] = {"format": {"type": "json_schema", "schema": strict_schema(schema)}}
    if tools:
        kw["tools"] = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t["parameters"],
            }
            for t in tools
        ]
    if s.get("cache"):
        kw["cache_control"] = {"type": "ephemeral"}  # automatic caching of the longest prefix
    kw["messages"] = [_anthropic_turn(m) for m in turns]
    return kw, unsupported


def _anthropic_turn(m: Message) -> Message:
    """Lantern's tool turns (role "tool", and assistant tool_calls) in Anthropic's block form."""
    if m["role"] == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": m["content"],
                }
            ],
        }
    if m["role"] == "assistant" and m.get("tool_calls"):
        blocks: list[dict[str, Any]] = []
        if m.get("content"):
            blocks.append({"type": "text", "text": m["content"]})
        for c in m["tool_calls"]:
            fn = c["function"]
            blocks.append(
                {
                    "type": "tool_use",
                    "id": c.get("id", ""),
                    "name": fn["name"],
                    "input": fn["arguments"],
                }
            )
        return {"role": "assistant", "content": blocks}
    return {"role": m["role"], "content": m["content"]}


def anthropic_reply(r: Any, model: str, unsupported: list[str]) -> Reply:
    text = "".join(b.text for b in r.content if b.type == "text")
    thinking = "".join(getattr(b, "thinking", "") or "" for b in r.content if b.type == "thinking")
    calls = [ToolCall(b.name, dict(b.input), b.id) for b in r.content if b.type == "tool_use"]
    u = r.usage
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    write = getattr(u, "cache_creation_input_tokens", 0) or 0
    return Reply(
        text.strip(),
        model,
        thinking=thinking,
        # Anthropic's input_tokens counts only the uncached part; Reply counts every input token.
        prompt_tokens=u.input_tokens + read + write,
        output_tokens=u.output_tokens,
        cached_tokens=read,
        cache_write_tokens=write,
        tool_calls=calls,
        unsupported=unsupported,
        stop_reason=r.stop_reason or "",
        raw={"id": getattr(r, "id", "")},
    )


def _anthropic(messages, model, s, format, tools, timeout) -> Reply:
    import anthropic

    kw, unsupported = anthropic_request(messages, model, s, format, tools)
    # The SDK's own retries are off: lantern.retry owns retries, so every attempt is counted.
    client = anthropic.Anthropic(api_key=_key("ANTHROPIC_API_KEY"), timeout=timeout, max_retries=0)
    try:
        r = client.messages.create(**kw)
    except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
        after = e.response.headers.get("retry-after") if e.response is not None else None
        raise retry.Transient(str(e), float(after) if after else None) from e
    except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
        raise retry.Transient(str(e)) from e
    except anthropic.APIStatusError as e:
        if e.status_code >= 500:
            raise retry.Transient(str(e)) from e
        raise
    if r.stop_reason == "refusal":
        print(f"[hosted] {model} declined this request (stop_reason=refusal)", file=sys.stderr)
    return anthropic_reply(r, model, unsupported)


# ---- OpenAI -----------------------------------------------------------------------------------


def openai_request(messages, model, s, format, tools) -> tuple[dict[str, Any], list[str]]:
    sup = load_config()["hosted"]["openai"].get("supports", {})
    unsupported: list[str] = []
    kw: dict[str, Any] = {"model": model, "max_completion_tokens": s["max_tokens"]}
    kw["messages"] = [_openai_turn(m) for m in messages]
    for name in ("temperature", "top_p", "seed"):
        if sup.get(name):
            kw[name] = s[name]
        else:
            unsupported.append(name)
    unsupported.append("top_k")  # the OpenAI API has no top_k
    if s.get("logprobs"):
        if sup.get("logprobs"):
            kw["logprobs"] = True
            kw["top_logprobs"] = s["logprobs"]
        else:
            unsupported.append("logprobs")
    if sup.get("reasoning_effort"):
        kw["reasoning_effort"] = "medium" if s["think"] else "minimal"
    elif s["think"]:
        unsupported.append("think")
    if format is not None:
        schema = format if isinstance(format, dict) else {"type": "object"}
        kw["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": strict_schema(schema), "strict": True},
        }
    if tools:
        kw["tools"] = [{"type": "function", "function": t} for t in tools]
    if s.get("cache"):
        # OpenAI caches long prefixes automatically; a stable key routes repeats together.
        kw["prompt_cache_key"] = "lantern"
    return kw, unsupported


def _openai_turn(m: Message) -> Message:
    if m["role"] == "assistant" and m.get("tool_calls"):
        return {
            "role": "assistant",
            "content": m.get("content") or None,
            "tool_calls": [
                {
                    "id": c.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": c["function"]["name"],
                        "arguments": json.dumps(c["function"]["arguments"]),
                    },
                }
                for c in m["tool_calls"]
            ],
        }
    if m["role"] == "tool":
        return {"role": "tool", "tool_call_id": m.get("tool_call_id", ""), "content": m["content"]}
    return {"role": m["role"], "content": m["content"]}


def openai_reply(r: Any, model: str, unsupported: list[str]) -> Reply:
    msg = r.choices[0].message
    calls = [
        ToolCall(c.function.name, json.loads(c.function.arguments or "{}"), c.id)
        for c in (msg.tool_calls or [])
    ]
    u = r.usage
    details = getattr(u, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    lp = []
    if getattr(r.choices[0], "logprobs", None) and r.choices[0].logprobs.content:
        lp = [{"token": t.token, "logprob": t.logprob} for t in r.choices[0].logprobs.content]
    return Reply(
        (msg.content or "").strip(),
        model,
        prompt_tokens=u.prompt_tokens,
        output_tokens=u.completion_tokens,
        cached_tokens=cached,
        tool_calls=calls,
        logprobs=lp,
        unsupported=unsupported,
        stop_reason=r.choices[0].finish_reason or "",
    )


def _openai(messages, model, s, format, tools, timeout) -> Reply:
    import openai

    kw, unsupported = openai_request(messages, model, s, format, tools)
    client = openai.OpenAI(api_key=_key("OPENAI_API_KEY"), timeout=timeout, max_retries=0)
    try:
        r = client.chat.completions.create(**kw)
    except (
        openai.RateLimitError,
        openai.InternalServerError,
        openai.APITimeoutError,
        openai.APIConnectionError,
    ) as e:
        raise retry.Transient(str(e)) from e
    return openai_reply(r, model, unsupported)


# ---- Gemini -----------------------------------------------------------------------------------


def gemini_request(messages, model, s, format, tools) -> tuple[dict[str, Any], list[str]]:
    sup = load_config()["hosted"]["gemini"].get("supports", {})
    system, turns = _split(messages)
    unsupported: list[str] = []
    config: dict[str, Any] = {"max_output_tokens": s["max_tokens"]}
    if system:
        config["system_instruction"] = system
    for name in ("temperature", "top_k", "top_p", "seed"):
        if sup.get(name):
            config[name] = s[name]
        else:
            unsupported.append(name)
    if s.get("logprobs"):
        if sup.get("logprobs"):
            config["response_logprobs"] = True
            config["logprobs"] = s["logprobs"]
        else:
            unsupported.append("logprobs")
    if sup.get("thinking"):
        config["thinking_config"] = {
            "thinking_budget": -1 if s["think"] else 0,
            "include_thoughts": bool(s["think"]),
        }
    if format is not None:
        config["response_mime_type"] = "application/json"
        if isinstance(format, dict):
            config["response_json_schema"] = format
    if tools:
        config["tools"] = [
            {
                "function_declarations": [
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters_json_schema": t["parameters"],
                    }
                    for t in tools
                ]
            }
        ]
    # Gemini caches repeated prefixes implicitly on its current models; `cache` needs nothing.
    contents = []
    for m in turns:
        if m["role"] == "tool":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": m.get("name", ""),
                                "response": {"result": m["content"]},
                            }
                        }
                    ],
                }
            )
        elif m["role"] == "assistant" and m.get("tool_calls"):
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        {
                            "function_call": {
                                "name": c["function"]["name"],
                                "args": c["function"]["arguments"],
                            }
                        }
                        for c in m["tool_calls"]
                    ],
                }
            )
        else:
            contents.append(
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
            )
    return {"model": model, "contents": contents, "config": config}, unsupported


def gemini_reply(r: Any, model: str, unsupported: list[str]) -> Reply:
    u = r.usage_metadata
    parts = r.candidates[0].content.parts if r.candidates else []
    text = "".join(
        p.text or "" for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)
    )
    thinking = "".join(p.text or "" for p in parts if getattr(p, "thought", False))
    calls = [
        ToolCall(p.function_call.name, dict(p.function_call.args or {}))
        for p in parts
        if getattr(p, "function_call", None)
    ]
    return Reply(
        text.strip(),
        model,
        thinking=thinking,
        prompt_tokens=u.prompt_token_count or 0,
        output_tokens=(u.candidates_token_count or 0) + (u.thoughts_token_count or 0),
        cached_tokens=u.cached_content_token_count or 0,
        tool_calls=calls,
        unsupported=unsupported,
        stop_reason=str(r.candidates[0].finish_reason) if r.candidates else "",
    )


def _gemini(messages, model, s, format, tools, timeout) -> Reply:
    from google import genai
    from google.genai import errors

    kw, unsupported = gemini_request(messages, model, s, format, tools)
    client = genai.Client(
        api_key=_key("GEMINI_API_KEY"), http_options={"timeout": int(timeout * 1000)}
    )
    try:
        r = client.models.generate_content(**kw)
    except errors.ServerError as e:
        raise retry.Transient(str(e)) from e
    except errors.ClientError as e:
        if getattr(e, "code", 0) == 429:
            raise retry.Transient(str(e)) from e
        raise
    return gemini_reply(r, model, unsupported)

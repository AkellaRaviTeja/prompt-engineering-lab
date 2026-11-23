"""One function, `chat`, that every lesson uses to talk to a model.

It returns a `Reply` with the text, the thinking (if any), any tool calls, token counts
(including cached tokens), the cost, the full latency and, on Ollama, the log-probabilities of
each generated token.

Every call:
- has a timeout, and retries with exponential backoff and full jitter on rate limits, server
  errors, timeouts and dropped connections (`lantern.retry`);
- measures latency on the wall clock, so `seconds` includes model load and prompt processing,
  with Ollama's own breakdown in `load_seconds`, `prompt_seconds` and `eval_seconds`;
- is logged with its prompt version, model, tokens, cost and latency (`lantern.calllog`), and
  traced as an OpenTelemetry span with GenAI attributes (`lantern.trace`).

The tier decides where it runs: `local` (Ollama, the default) or `hosted` (`TIER=hosted`, a
provider's API through `lantern.cloud`, synthetic material only).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from lantern import calllog, retry, trace
from lantern.config import load_config, model_name, price_of, provider_of

Message = dict[str, Any]


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass
class Reply:
    text: str
    model: str
    thinking: str = ""
    prompt_tokens: int = 0  # every input token, cached or not
    output_tokens: int = 0
    cached_tokens: int = 0  # input tokens read from a prompt cache
    cache_write_tokens: int = 0  # input tokens written to a prompt cache
    seconds: float = 0.0  # wall clock for the whole call: load, prompt processing, generation
    load_seconds: float = 0.0
    prompt_seconds: float = 0.0
    eval_seconds: float = 0.0  # generation only
    logprobs: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = "ollama"
    cost_usd: float | None = 0.0  # None when the model has no checked price in config.yaml
    attempts: int = 1
    unsupported: list[str] = field(default_factory=list)  # settings the provider could not take
    prompt_version: str = ""
    stop_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_per_second(self) -> float:
        """Generation speed: output tokens over generation time (wall clock if unknown)."""
        t = self.eval_seconds or self.seconds
        return self.output_tokens / t if t else 0.0

    def json(self) -> Any:
        """Parse the reply text as JSON (for structured output)."""
        return json.loads(self.text)


def chat(
    messages: list[Message] | str,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    top_k: int | None = None,
    top_p: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_tokens: int | None = None,
    think: bool | None = None,
    format: dict[str, Any] | str | None = None,
    logprobs: int = 0,
    tools: list[dict[str, Any]] | None = None,
    cache: bool = False,
    timeout: float | None = None,
    retries: int | None = None,
    prompt_version: str | None = None,
) -> Reply:
    """Send a conversation to the configured tier and return a Reply.

    `messages` may be a plain string (one user turn) or a list of
    {"role": ..., "content": ...} dicts. `system` is prepended as a system message.
    Any generation setting left as None falls back to config.yaml.

    `tools` are JSON-schema function definitions ({"name", "description", "parameters"});
    the model's calls come back in `Reply.tool_calls`. `cache=True` asks a hosted provider to
    cache the prompt prefix (Ollama keeps its own KV cache and ignores it).
    `prompt_version` labels the call in the log; without it the label is a hash of the system
    prompt, schema and tools, so a changed prompt gets a new version.
    """
    cfg = load_config()
    gen = cfg["generation"]
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    if system:
        messages = [{"role": "system", "content": system}, *messages]

    explicit = {
        k
        for k, v in {
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "seed": seed,
            "think": think,
        }.items()
        if v is not None
    }
    if logprobs:
        explicit.add("logprobs")
    settings = {
        "temperature": gen["temperature"] if temperature is None else temperature,
        "top_k": gen["top_k"] if top_k is None else top_k,
        "top_p": gen["top_p"] if top_p is None else top_p,
        "seed": gen["seed"] if seed is None else seed,
        "num_ctx": gen["num_ctx"] if num_ctx is None else num_ctx,
        "max_tokens": gen["max_tokens"] if max_tokens is None else max_tokens,
        "think": gen["think"] if think is None else think,
        "logprobs": logprobs,
        "explicit": explicit,
        "cache": cache,
    }
    rcfg = cfg.get("reliability", {})
    timeout = rcfg.get("timeout_s", 300) if timeout is None else timeout
    retries = rcfg.get("retries", 3) if retries is None else retries
    provider = provider_of(cfg)
    name = model_name(model)
    version = prompt_version or calllog.prompt_hash(messages, format, tools)

    def once() -> Reply:
        if provider == "ollama":
            return _ollama(messages, name, settings, format, tools, timeout)
        from lantern import cloud

        return cloud.chat(provider, messages, name, settings, format, tools, timeout)

    with trace.span(f"chat {name}", **trace.request_attrs(provider, name, settings)) as sp:
        start = time.perf_counter()
        reply, attempts = retry.call(
            once, retries=retries, base=rcfg.get("backoff_base_s", 1.0),
            cap=rcfg.get("backoff_cap_s", 30.0),
        )
        reply.seconds = time.perf_counter() - start
        reply.attempts = attempts
        reply.provider = provider
        reply.prompt_version = version
        reply.cost_usd = cost_of(reply)
        trace.set_response(sp, reply)
    calllog.log(reply)
    return reply


def cost_of(r: Reply) -> float | None:
    """USD for one reply from config.yaml prices. 0 on the local tier; None if unpriced."""
    if r.provider == "ollama":
        return 0.0
    p = price_of(r.model)
    if p is None:
        return None
    if "over" in p and r.prompt_tokens > p["over"]["tokens"]:
        p = p["over"]  # a long prompt is billed at the higher prices, the whole request
    uncached = max(r.prompt_tokens - r.cached_tokens - r.cache_write_tokens, 0)
    return (
        uncached * p["input"]
        + r.cached_tokens * p.get("cache_read", p["input"])
        + r.cache_write_tokens * p.get("cache_write", p["input"])
        + r.output_tokens * p["output"]
    ) / 1e6


def _ollama(
    messages: list[Message],
    model: str,
    s: dict[str, Any],
    format: dict[str, Any] | str | None,
    tools: list[dict[str, Any]] | None,
    timeout: float,
) -> Reply:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": s["think"],
        "options": {
            "temperature": s["temperature"],
            "top_k": s["top_k"],
            "top_p": s["top_p"],
            "num_ctx": s["num_ctx"],
            "num_predict": s["max_tokens"],
        },
    }
    if s["seed"] is not None:
        body["options"]["seed"] = s["seed"]
    if format is not None:
        body["format"] = format
    if s["logprobs"]:
        body["logprobs"] = True
        body["top_logprobs"] = s["logprobs"]
    if tools:
        body["tools"] = [{"type": "function", "function": t} for t in tools]
    host = load_config()["ollama"]["host"]
    try:
        r = httpx.post(f"{host}/api/chat", json=body, timeout=timeout)
    except httpx.ConnectError as e:
        raise retry.Transient(
            f"Cannot reach Ollama at {host}. Start it with `make up` (Docker) or `ollama serve`."
        ) from e
    except httpx.TimeoutException as e:
        raise retry.Transient(f"Ollama did not answer within {timeout:.0f}s") from e
    if r.status_code == 404:
        raise SystemExit(f"Model {model!r} is not pulled. Run `make models`.")
    if r.status_code == 429 or r.status_code >= 500:
        detail = r.text.strip()[:300] if isinstance(getattr(r, "text", None), str) else ""
        raise retry.Transient(f"Ollama returned HTTP {r.status_code}" + (f": {detail}" if detail
                                                                          else ""))
    r.raise_for_status()
    data = r.json()
    msg = data["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function", {})
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"_unparsed": args}
        calls.append(ToolCall(fn.get("name", ""), args, c.get("id", "")))
    return Reply(
        text=msg.get("content", "").strip(),
        thinking=msg.get("thinking", "") or "",
        model=model,
        prompt_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        seconds=data.get("total_duration", 0) / 1e9,
        load_seconds=data.get("load_duration", 0) / 1e9,
        prompt_seconds=data.get("prompt_eval_duration", 0) / 1e9,
        eval_seconds=data.get("eval_duration", 0) / 1e9,
        logprobs=data.get("logprobs") or [],
        tool_calls=calls,
        stop_reason=data.get("done_reason", ""),
        raw=data,
    )


def model_info(model: str | None = None) -> dict[str, Any]:
    """Ollama's /api/show: the chat template, parameters and architecture details.

    Local tier only: a hosted provider does not publish its chat template or weights.
    """
    if provider_of() != "ollama":
        raise SystemExit("model_info() reads Ollama's model file; it has no hosted equivalent.")
    host = load_config()["ollama"]["host"]
    r = httpx.post(f"{host}/api/show", json={"model": model_name(model)}, timeout=60)
    r.raise_for_status()
    return r.json()


def context_length(model: str | None = None) -> int:
    """The maximum context the model was trained for, read from its metadata.

    On the hosted tier, the provider's documented window from config.yaml.
    """
    provider = provider_of()
    if provider != "ollama":
        return int(load_config()["hosted"][provider].get("context_window", {}).get(
            model_name(model), 0))
    info = model_info(model).get("model_info", {})
    for key, value in info.items():
        if key.endswith(".context_length"):
            return int(value)
    return 0

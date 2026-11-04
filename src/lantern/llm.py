"""One function, `chat`, that every lesson uses to talk to a model.

It returns a `Reply` with the text, the thinking (if any), token counts, timings
and, on Ollama, the log-probabilities of each generated token.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from lantern.config import load_config, model_name

Message = dict[str, str]


@dataclass
class Reply:
    text: str
    model: str
    thinking: str = ""
    prompt_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    logprobs: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_per_second(self) -> float:
        return self.output_tokens / self.seconds if self.seconds else 0.0

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
) -> Reply:
    """Send a conversation to the configured provider and return a Reply.

    `messages` may be a plain string (one user turn) or a list of
    {"role": ..., "content": ...} dicts. `system` is prepended as a system message.
    Any generation setting left as None falls back to config.yaml.
    """
    cfg = load_config()
    gen = cfg["generation"]
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    if system:
        messages = [{"role": "system", "content": system}, *messages]

    settings = {
        "temperature": gen["temperature"] if temperature is None else temperature,
        "top_k": gen["top_k"] if top_k is None else top_k,
        "top_p": gen["top_p"] if top_p is None else top_p,
        "seed": gen["seed"] if seed is None else seed,
        "num_ctx": gen["num_ctx"] if num_ctx is None else num_ctx,
        "max_tokens": gen["max_tokens"] if max_tokens is None else max_tokens,
        "think": gen["think"] if think is None else think,
    }
    provider = cfg["provider"]
    if provider == "ollama":
        return _ollama(messages, model_name(model), settings, format, logprobs)
    from lantern import cloud

    return cloud.chat(provider, messages, settings, format)


def _ollama(
    messages: list[Message],
    model: str,
    s: dict[str, Any],
    format: dict[str, Any] | str | None,
    logprobs: int,
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
    if logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = logprobs
    host = load_config()["ollama"]["host"]
    try:
        r = httpx.post(f"{host}/api/chat", json=body, timeout=600)
    except httpx.ConnectError as e:
        raise SystemExit(
            f"Cannot reach Ollama at {host}. Start it with `make up` (Docker) or `ollama serve`."
        ) from e
    if r.status_code == 404:
        raise SystemExit(f"Model {model!r} is not pulled. Run `make models`.")
    r.raise_for_status()
    data = r.json()
    msg = data["message"]
    return Reply(
        text=msg.get("content", "").strip(),
        thinking=msg.get("thinking", "") or "",
        model=model,
        prompt_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        seconds=data.get("eval_duration", 0) / 1e9,
        logprobs=data.get("logprobs") or [],
        raw=data,
    )


def model_info(model: str | None = None) -> dict[str, Any]:
    """Ollama's /api/show: the chat template, parameters and architecture details."""
    host = load_config()["ollama"]["host"]
    r = httpx.post(f"{host}/api/show", json={"model": model_name(model)}, timeout=60)
    r.raise_for_status()
    return r.json()


def context_length(model: str | None = None) -> int:
    """The maximum context the model was trained for, read from its metadata."""
    info = model_info(model).get("model_info", {})
    for key, value in info.items():
        if key.endswith(".context_length"):
            return int(value)
    return 0

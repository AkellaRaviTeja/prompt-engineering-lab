"""Render a conversation into the exact text Qwen3 reads, and send it raw.

This mirrors the Qwen3 chat template that Ollama ships (system, user and assistant
turns, no tools). Lesson 04 proves it matches by comparing token counts and output
with the normal chat endpoint.
"""

from __future__ import annotations

import httpx

from lantern import load_config
from lantern.config import model_name


def render_chatml(messages: list[dict[str, str]], think: bool = False) -> str:
    out = []
    last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
    for i, m in enumerate(messages):
        content = m["content"]
        if i == last_user:
            content += " /think" if think else " /no_think"
        out.append(f"<|im_start|>{m['role']}\n{content}<|im_end|>\n")
    out.append("<|im_start|>assistant\n")
    if not think:
        out.append("<think>\n\n</think>\n\n")
    return "".join(out)


def generate_raw(prompt: str, **options) -> dict:
    """Ollama's /api/generate with raw=true: no template, the text goes in exactly as given."""
    cfg = load_config()
    gen = cfg["generation"]
    opts = {"temperature": gen["temperature"], "top_k": gen["top_k"], "top_p": gen["top_p"],
            "seed": gen["seed"], "num_ctx": gen["num_ctx"], "num_predict": gen["max_tokens"]}
    opts.update(options)
    r = httpx.post(f"{cfg['ollama']['host']}/api/generate", timeout=600, json={
        "model": model_name(None), "prompt": prompt, "raw": True, "stream": False,
        "options": opts})
    r.raise_for_status()
    return r.json()

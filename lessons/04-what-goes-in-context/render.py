"""Render a conversation into the exact text Qwen3 reads, and send it raw.

This mirrors the Qwen3 chat template that Ollama ships (system, user and assistant
turns, no tools). Lesson 04 proves it matches by comparing token counts and output
with the normal chat endpoint.
"""

from __future__ import annotations

from lantern import llm
from lantern.llm import Reply


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


def generate_raw(prompt: str, **options) -> Reply:
    """Ollama's /api/generate with raw=true: no template, the text goes in exactly as given.

    It goes through `lantern.llm.generate_raw`, so it has the shared timeout, retries, call log
    and trace span that every `chat` call has.
    """
    return llm.generate_raw(prompt, **options)

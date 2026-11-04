"""Optional cloud providers. Install with `uv sync --extra cloud` and set a key in .env.

In the story, evidence never leaves the building. In the lab these adapters let you
compare a local model's answer with a frontier model's answer on the same prompt.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from lantern.config import load_config
from lantern.llm import Message, Reply


def chat(
    provider: str,
    messages: list[Message],
    s: dict[str, Any],
    format: dict[str, Any] | str | None,
) -> Reply:
    model = load_config()["cloud"][provider]["model"]
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [m for m in messages if m["role"] != "system"]
    if format is not None:
        schema = format if isinstance(format, dict) else {"type": "object"}
        system += f"\n\nReply with JSON only, matching this schema:\n{json.dumps(schema)}"
    start = time.perf_counter()

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        r = client.messages.create(
            model=model,
            system=system or anthropic.NOT_GIVEN,
            messages=turns,
            max_tokens=s["max_tokens"],
            temperature=s["temperature"],
            top_k=s["top_k"],
        )
        text = "".join(b.text for b in r.content if b.type == "text")
        return Reply(text, model, prompt_tokens=r.usage.input_tokens,
                     output_tokens=r.usage.output_tokens,
                     seconds=time.perf_counter() - start)

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        msgs = ([{"role": "system", "content": system}] if system else []) + turns
        r = client.chat.completions.create(
            model=model, messages=msgs, max_completion_tokens=s["max_tokens"], seed=s["seed"]
        )
        return Reply(r.choices[0].message.content or "", model,
                     prompt_tokens=r.usage.prompt_tokens,
                     output_tokens=r.usage.completion_tokens,
                     seconds=time.perf_counter() - start)

    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in turns
        ]
        r = client.models.generate_content(
            model=model, contents=contents,
            config={"system_instruction": system or None, "temperature": s["temperature"],
                    "top_k": s["top_k"], "max_output_tokens": s["max_tokens"]},
        )
        u = r.usage_metadata
        return Reply(r.text or "", model, prompt_tokens=u.prompt_token_count or 0,
                     output_tokens=u.candidates_token_count or 0,
                     seconds=time.perf_counter() - start)

    raise SystemExit(f"Unknown provider {provider!r}. Use ollama, anthropic, openai or gemini.")

"""A scripted model for offline tests and exercises: no Ollama needed.

    model = Scripted([say(calls=[("money_out", {"account_holder": "Arden"})]), say("done")])
    reply = model(messages, tools=TOOLS)      # same shape as lantern.chat
    Scripted([Transient("429"), say("ok")])   # an exception in the script is raised, in order
    model.requests                            # every request it was sent, copied

Exercises take the model as an argument (`chat=`), so the tests hand them a Scripted model and
`make lesson N=NN ARGS=--mine` hands them the real `lantern.chat`.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from lantern.llm import Reply, ToolCall

__all__ = ["Scripted", "say"]


def say(
    text: str = "",
    calls: list[tuple[str, dict[str, Any]]] | tuple = (),
    *,
    prompt: int = 100,
    out: int = 10,
    cached: int = 0,
    thinking: str = "",
) -> Reply:
    """One model reply: some text, some tool calls, or both, with token counts."""
    msg: dict[str, Any] = {"role": "assistant", "content": text}
    if calls:
        msg["tool_calls"] = [{"function": {"name": n, "arguments": a}} for n, a in calls]
    return Reply(
        text,
        "scripted",
        tool_calls=[ToolCall(n, dict(a)) for n, a in calls],
        thinking=thinking,
        prompt_tokens=prompt,
        output_tokens=out,
        cached_tokens=cached,
        raw={"message": msg},
    )


class Scripted:
    """A fake `chat`: returns the scripted replies in order and records every request."""

    def __init__(self, replies: list[Reply | BaseException]):
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Reply:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        self.requests.append({"messages": copy.deepcopy(list(messages)), **kwargs})
        if not self.replies:
            raise AssertionError(
                f"the model was called {len(self.requests)} times, more than the test scripted"
            )
        nxt = self.replies.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt  # a scripted failure: a rate limit, a timeout
        return nxt

    @property
    def calls(self) -> int:
        return len(self.requests)

    def last_tool_results(self) -> list[Any]:
        """The tool messages in the latest request, decoded from JSON where possible."""
        out = []
        for m in self.requests[-1]["messages"]:
            if m.get("role") == "tool":
                try:
                    out.append(json.loads(m["content"]))
                except (TypeError, ValueError):
                    out.append(m["content"])
        return out

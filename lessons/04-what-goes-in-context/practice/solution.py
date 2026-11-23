"""Chapter 04 reference solution: the context assembler. Compare it with yours."""

from __future__ import annotations

from collections.abc import Callable


def approx_tokens(text: str) -> int:
    """A rough count for budgeting before a call: about four characters per token."""
    return (len(text) + 3) // 4


def assemble(
    *,
    rules: str,
    summary: str,
    documents: list[tuple[str, str]],
    history: list[dict[str, str]],
    question: str,
    budget: int,
    count: Callable[[str], int] = approx_tokens,
) -> dict:
    """The briefing as messages, trimmed to `budget`. Returns {"messages", "dropped", "tokens"}."""
    docs, hist, dropped = list(documents), list(history), []

    def render() -> list[dict[str, str]]:
        brief = f"<case_summary>\n{summary.rstrip()}\n</case_summary>"
        if docs:
            files = "".join(f'<file name="{n}">\n{t.rstrip()}\n</file>\n' for n, t in docs)
            brief += f"\n\n<evidence>\n{files}</evidence>"
        return [
            {"role": "system", "content": rules},
            {"role": "user", "content": brief + "\n\nBriefing received?"},
            {"role": "assistant", "content": "Briefing received."},
            *hist,
            {"role": "user", "content": question},
        ]

    def size(msgs: list[dict[str, str]]) -> int:
        return sum(count(m["content"]) for m in msgs)

    msgs = render()
    while size(msgs) > budget and hist:
        dropped.append("history: " + hist[0]["content"][:40])
        hist = hist[2:]  # one exchange: the question and its answer
        msgs = render()
    while size(msgs) > budget and docs:
        dropped.append(docs.pop()[0])  # the least important document
        msgs = render()
    if size(msgs) > budget:
        raise ValueError(f"rules, summary and question alone need {size(msgs)} of {budget}")
    return {"messages": msgs, "dropped": dropped, "tokens": size(msgs)}

"""Chapter 04 exercise: the context assembler. Brief LANTERN the way Varma briefs a room.

Rules, case summary, the documents that matter, the conversation so far, and the question last,
each part labelled, the whole trimmed to a token budget in a stated order of importance.

Fill in `assemble`. Grade it with `make exercise N=04` (offline: no model is called). Then run
the live lesson on your assembler: `make lesson N=04 ARGS=--mine`. Stuck? `make hint N=04`.
"""

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
    """The briefing as messages, trimmed to `budget`. Returns {"messages", "dropped", "tokens"}.

    The messages, in this order:
        system     rules
        user       "<case_summary>\\n{summary}\\n</case_summary>", then a blank line and
                   "<evidence>\\n" + one '<file name="{name}">\\n{text}\\n</file>\\n' per
                   document + "</evidence>" (no evidence block if there are no documents),
                   then "\\n\\nBriefing received?"  (strip trailing whitespace from summary and
                   each text)
        assistant  "Briefing received."
        ...        the history turns, unchanged
        user       question, exactly

    `documents` is a list of (name, text), most important first. The size of the briefing is
    the sum of count(content) over every message. While it is over `budget`:
        1. drop the oldest exchange of history (two turns: a question and its answer), and add
           "history: " + the first 40 characters of that question to `dropped`;
        2. once the history is gone, drop the last document, and add its name to `dropped`.
    Rules, summary and question are never dropped: if they alone exceed the budget, raise
    ValueError. `tokens` is the final size.
    """
    # TODO 1: write render(docs, history) that builds the message list above.
    # TODO 2: write size(messages): the sum of count() over every message's content.
    # TODO 3: trim history, oldest exchange first, while over budget.
    # TODO 4: then trim documents from the end, while over budget.
    # TODO 5: still over budget: ValueError. Otherwise return the dict.
    raise NotImplementedError("TODO 1 to 5: assemble the briefing")

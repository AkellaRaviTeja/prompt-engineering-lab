"""Chapter 02 exercise: write the standing orders, and the code that enforces them.

A system prompt is a strong preference, not a lock. So the orders get a second half in code:
an answer that does not cite the evidence word for word is replaced by exactly NOT IN EVIDENCE.

Fill in ORDERS, `cited`, `enforce` and `answer`. Grade them with `make exercise N=02` (offline:
the tests use a scripted model). When every test passes, run the live lesson on your code:
`make lesson N=02 ARGS=--mine`. Stuck? `make hint N=02`.
"""

from __future__ import annotations

import re  # noqa: F401  (the solution uses it)
from collections.abc import Callable
from typing import Any

NOT_IN_EVIDENCE = "NOT IN EVIDENCE."
MIN_QUOTE_WORDS = 4  # "I. Petrov" is a real string from the file, and supports nothing

# TODO 1: write the standing orders. They must say to answer only from the <evidence>, to cite
#         every fact as [file name: "exact quote"] (show a real file name, such as petrov.md, in
#         the example: a small model copies the example literally), and to reply exactly
#         NOT IN EVIDENCE when the documents do not answer.
ORDERS = ""


def cited(answer: str) -> list[tuple[str, str]]:
    """Every [file: "quote"] citation in an answer, as (file, quote) pairs, in order.

    [petrov.md: "two minutes on foot"] gives ("petrov.md", "two minutes on foot").
    """
    # TODO 2: find every citation with a regular expression.
    raise NotImplementedError("TODO 2: find the citations")


def enforce(answer: str, documents: dict[str, str]) -> str:
    """The answer if it is cited from the evidence; otherwise exactly NOT_IN_EVIDENCE.

    The answer stands only if all of these hold:
    - it does not start with NOT IN EVIDENCE (if it does, return NOT_IN_EVIDENCE alone:
      no theories after it survive);
    - it has at least one citation;
    - every citation names a file in `documents`, quotes at least MIN_QUOTE_WORDS words, and
      the quote appears in that file word for word. Compare ignoring case, `*` and the
      difference between spaces and line breaks: the files are hard-wrapped.
    A standing answer is returned stripped of surrounding whitespace.
    """
    # TODO 3: a declined answer becomes NOT_IN_EVIDENCE alone.
    # TODO 4: no citations, or any bad citation, means NOT_IN_EVIDENCE.
    raise NotImplementedError("TODO 3 and 4: enforce the orders")


def answer(question: str, documents: dict[str, str], *, chat: Callable[..., Any]) -> dict:
    """Ask under ORDERS, then enforce them. Returns {"raw", "text", "held"}.

    The user turn carries the documents inside <evidence>, each as <file name="...">, then the
    question inside <question> tags, then "Apply the standing orders." Call
    `chat(prompt, system=ORDERS, temperature=0, max_tokens=300)`.
    raw   the model's reply text
    text  what enforce() lets through
    held  True if the model's reply stood unchanged
    """
    # TODO 5: build the user turn, call the model once, enforce, return the dict.
    raise NotImplementedError("TODO 5: ask and enforce")

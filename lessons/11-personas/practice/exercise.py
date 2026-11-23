"""Chapter 11 exercise: standing orders above a persona, and a check that the reply kept them.

A persona sets the voice. The standing orders set the limits, and they must sit above the role
in the system prompt, where no role can remove them. Then, because a prompt is not a guarantee,
check the reply: any time, amount or reference the evidence does not contain was invented.

Grade it with `make exercise N=11` (offline, no model). Stuck? `make hint N=11`.
Start again? `make exercise-reset N=11`.
"""

from __future__ import annotations

import re

PRECEDENCE = "If the role and the standing orders conflict, the standing orders win."

# One pattern for the three kinds of figure. Use FIGURE.finditer(text) to scan a reply in order.
FIGURE = re.compile(r"\b[A-Z]{1,4}(?:-[A-Z0-9]+)*-\d{2,}\b"  # a reference: NW-0419
                    r"|\b\d{1,2}:\d{2}(?::\d{2})?\b"            # a time: 23:31 or 23:31:02
                    r"|\d[\d,]*(?:\.\d+)?")                     # a number: 94,000.00
NUMBER = re.compile(r"[\d,]+(?:\.\d+)?")


def persona_system(orders: str, persona: str) -> str:
    """One system prompt: the standing orders first, the persona under them, the precedence rule
    last.

        <orders>

        Role for this request:
        <persona>

        If the role and the standing orders conflict, the standing orders win.

    Both texts are stripped of surrounding whitespace. Empty orders raise ValueError: a persona
    must never run without them.
    """
    # TODO 1: refuse empty (or whitespace-only) orders with ValueError.
    # TODO 2: return the orders, then "Role for this request:" and the persona, then PRECEDENCE,
    #         separated by blank lines exactly as in the docstring.
    raise NotImplementedError("TODO 1 and 2: persona_system")


def figures(text: str) -> list[str]:
    """References, times, and numbers of 100 or more or with decimals, in order of appearance."""
    # TODO 3: every FIGURE match, with a trailing comma stripped, except plain numbers below 100
    #         with no decimal point (list numbers and small counts).
    raise NotImplementedError("TODO 3: figures")


def broken_orders(reply: str, evidence: str) -> list[str]:
    """The figures in a persona's reply that are not in the evidence, each once, in reply order.

    A figure is a reference (NW-0419, OVR-AUD-02, B-0733), a time (23:31 or 23:31:02), or a
    number of 100 or more or with a decimal point. Numbers are compared by value, so 94,000.00
    matches 94000. A time matches the same time with seconds: 23:31 matches 23:31:02.
    """
    # TODO 4: the figures in the evidence, and the numeric values among them.
    # TODO 5: for each figure in the reply: a number is fine if its value is in the evidence; a
    #         time or reference is fine if the evidence has it exactly, or with seconds added.
    # TODO 6: return the ones that are not fine, each once, in the order the reply gives them.
    raise NotImplementedError("TODO 4 to 6: broken_orders")

"""Chapter 11 solution: standing orders above a persona, and a check that the reply kept them.
Read it once you have tried."""

from __future__ import annotations

import re

PRECEDENCE = "If the role and the standing orders conflict, the standing orders win."

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
    if not orders.strip():
        raise ValueError("a persona needs standing orders above it")
    return f"{orders.strip()}\n\nRole for this request:\n{persona.strip()}\n\n{PRECEDENCE}"


def figures(text: str) -> list[str]:
    """References, times, and numbers of 100 or more or with decimals, in order of appearance."""
    found = []
    for m in FIGURE.finditer(text):
        f = m.group().rstrip(",")
        if NUMBER.fullmatch(f) and "." not in f and float(f.replace(",", "")) < 100:
            continue  # list numbers and small counts
        found.append(f)
    return found


def broken_orders(reply: str, evidence: str) -> list[str]:
    """The figures in a persona's reply that are not in the evidence, each once, in reply order.

    A figure is a reference (NW-0419, OVR-AUD-02, B-0733), a time (23:31 or 23:31:02), or a
    number of 100 or more or with a decimal point. Numbers are compared by value, so 94,000.00
    matches 94000. A time matches the same time with seconds: 23:31 matches 23:31:02.
    """
    known = figures(evidence)
    values = {float(k.replace(",", "")) for k in known if NUMBER.fullmatch(k)}
    out: list[str] = []
    for f in figures(reply):
        if NUMBER.fullmatch(f):
            ok = float(f.replace(",", "")) in values
        else:
            ok = any(k == f or k.startswith(f + ":") for k in known)
        if not ok and f not in out:
            out.append(f)
    return out

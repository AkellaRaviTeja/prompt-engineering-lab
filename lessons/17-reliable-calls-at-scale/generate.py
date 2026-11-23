"""A seeded generator of synthetic intercepts, shaped like case/messages.jsonl.

Headquarters' load-test batch: every message is invented from the templates below, so the batch
is synthetic training material, never evidence. The same seed always gives the same batch.

    uv run python lessons/17-reliable-calls-at-scale/generate.py 5      # print five
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta

SEED = 1717

# Each label: senders, and templates whose {slots} are filled from FILL.
TEMPLATES = {
    "logistics": (
        ["Harbour control", "Pier 6 dispatch", "Accounts payable", "Crewing desk", "Customs broker",
         "Fleet office", "Site security", "Payroll", "Port authority", "Tug master"],
        [
            "Berth {n} is free from {hh}:00, bring the {ship} in early.",
            "Tugs confirmed for the {ship}, pier {n}, {hh}:{mm}.",
            "Invoice {inv} is {d} days overdue, please confirm payment date.",
            "Crew change for the {ship} moved to {day}, paperwork incomplete.",
            "Pilot boat delayed by fog, expect {d} minutes.",
            "Meeting with the port authority moved to {hh}:{mm}, room {n}.",
            "Your new badge is at reception, the old one stops working on {day}.",
            "Fuel delivery for the {ship} is short by {d} tonnes, please check.",
            "Can you sign off the overtime sheet before payroll closes on {day}?",
            "Customs released the {ship} cargo, collect the papers from gate {n}.",
        ],
    ),
    "personal": (
        ["Sam (brother)", "Mum", "Priya", "Coach Ellis", "Dr Rahman's surgery", "Jo (neighbour)",
         "Leo", "Aunt Mira", "Book club", "Tom"],
        [
            "Dinner at mine on {day}, bring {food}.",
            "{kid} lost a tooth today, call before bed.",
            "The dentist can see you on {day} at {hh}:{mm}.",
            "Football at {hh}, bring the spare shin pads.",
            "Happy birthday! Drinks on {day}, no excuses.",
            "Did you book the ferry for the summer? Prices go up on {day}.",
            "Mum says lunch on {day}, she is making {food}.",
            "{kid} has a school play on {day} at {hh}:{mm}, front row if you can.",
            "Your prescription is ready to collect from {day}.",
            "Running club moved to {hh}:{mm}, same route as last week.",
        ],
    ),
    "threat": (
        ["unknown +77 410", "unknown +77 902", "withheld", "unknown +61 220", "no caller ID"],
        [
            "It would be a shame if your questions reached the wrong people.",
            "We know which school {kid} goes to.",
            "Stop looking at the {ship} accounts. This is the only time we will ask.",
            "Think carefully about what goes in that report on {day}.",
            "Someone saw you at gate {n} on {day}. Why were you there?",
            "Your family's expenses must be hard to meet. Do not make them harder.",
            "Nice car. Shame about the road out of pier {n} at night.",
            "Keep asking about invoice {inv} and see what it costs you.",
            "You were at the registry at {hh}:{mm}. Do not go back.",
            "Leave the {ship} file alone. Last warning.",
        ],
    ),
}

FILL = {
    "ship": ["Aster Line vessel", "Coral Bay", "Mardale Star", "Grey Heron", "Lindqvist",
             "Pelican Reach", "Saltmarsh", "Northern Lark"],
    "day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "food": ["the lamb", "fish stew", "a salad", "dessert", "the bread"],
    "kid": ["Mia", "Leo", "Ana", "Theo"],
}

# Roughly the mix of the 48 real messages: mostly logistics, then personal, a few threats.
WEIGHTS = {"logistics": 0.5, "personal": 0.35, "threat": 0.15}


def _fill(template: str, rng: random.Random) -> str:
    slots = {k: rng.choice(v) for k, v in FILL.items()}
    slots |= {
        "n": rng.randint(1, 12),
        "hh": f"{rng.randint(6, 23):02d}",
        "mm": rng.choice(["00", "15", "30", "45"]),
        "d": rng.randint(10, 90),
        "inv": f"KT-{rng.randint(1000, 9999)}",
    }
    return template.format(**slots)


def messages(n: int, seed: int = SEED) -> list[dict]:
    """`n` synthetic messages with gold labels, the same for the same seed."""
    rng = random.Random(seed)
    labels, weights = zip(*WEIGHTS.items(), strict=True)
    start = datetime(2026, 10, 1, 7, 0)
    out = []
    for i in range(n):
        label = rng.choices(labels, weights)[0]
        senders, templates = TEMPLATES[label]
        when = start + timedelta(minutes=rng.randint(0, 31 * 24 * 60 - 1))
        out.append({
            "id": f"S{i + 1:05d}",
            "time": when.strftime("%Y-%m-%d %H:%M"),
            "from": rng.choice(senders),
            "text": _fill(rng.choice(templates), rng),
            "label": label,
        })
    return out


if __name__ == "__main__":
    for m in messages(int(sys.argv[1]) if len(sys.argv) > 1 else 5):
        print(json.dumps(m))

"""Chapter 10 solution: who could have opened the door, decided by code. Read it once you have
tried."""

from __future__ import annotations

import csv
import io
from typing import Any


def minutes(t: str) -> int:
    """'23:36:15' or '18:00' -> minutes after midnight (seconds dropped)."""
    h, m = (int(x) for x in t.split(":")[:2])
    return h * 60 + m


def door_candidates(
    log_csv: str,
    *,
    door: str,
    at: str,
    overrides: dict[str, dict[str, Any]],
    alibis: dict[str, str | None],
) -> dict[str, Any]:
    """Who could have opened `door` from the outside at time `at`.

    `log_csv` is the badge log (case/badge-log.csv). `overrides` maps each override code to
    {"holder": name, "valid": ("HH:MM", "HH:MM") or None for no time limit}. `alibis` maps each
    person to where the records place them at that moment, or None when nothing does.

    Returns:
        credential     the badge_id on the log row for `door`, direction "in", at `at`
        could          who held that credential while it was valid at `at`
        ruled_out      {name: reason} for every other code holder and every person with an alibi
        not_ruled_out  people with no alibi who did not hold the credential (they could have
                       been given it)

    Raises ValueError when the log has no such row.
    """
    row = next(
        (r for r in csv.DictReader(io.StringIO(log_csv))
         if r["door"] == door and r["time"] == at and r["direction"] == "in"),
        None,
    )
    if row is None:
        raise ValueError(f"no entry through {door} at {at} in the log")
    cred = row["badge_id"]

    could: list[str] = []
    ruled_out: dict[str, str] = {}
    for code, o in overrides.items():
        start, end = o["valid"] or ("00:00", "23:59")
        valid = minutes(start) <= minutes(at) <= minutes(end)
        hours = "" if o["valid"] is None else f"valid {o['valid'][0]} to {o['valid'][1]} only"
        if code == cred and valid:
            could.append(o["holder"])
        elif code == cred:
            ruled_out[o["holder"]] = f"{code} is {hours}"
        else:
            ruled_out[o["holder"]] = f"{code} was not used" + (f", and is {hours}" if hours else "")
    if cred not in overrides:
        could.append(row["holder"])  # a badge: the log names its holder

    for person, alibi in alibis.items():
        if person not in could and alibi:
            ruled_out[person] = alibi
    not_ruled_out = [p for p, a in alibis.items() if not a and p not in could]
    return {"credential": cred, "could": could, "ruled_out": ruled_out,
            "not_ruled_out": not_ruled_out}

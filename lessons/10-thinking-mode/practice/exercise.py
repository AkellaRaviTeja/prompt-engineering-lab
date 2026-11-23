"""Chapter 10 exercise: who could have opened the door, decided by code.

A thinking model spent thousands of tokens on this question and still got it wrong. The records
decide it in a dozen lines. Write those lines: the deterministic check the chapter scores every
model answer against (step 5 of run.py).

Grade it with `make exercise N=10` (offline). Stuck? `make hint N=10`.
Start again? `make exercise-reset N=10`.
"""

from __future__ import annotations

import csv  # noqa: F401  (the solution uses it)
import io  # noqa: F401
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
    # TODO 1: find the log row for `door` at `at` with direction "in" (csv.DictReader over
    #         io.StringIO). No row: raise ValueError. Its badge_id is the credential.
    # TODO 2: for each override code: its holder COULD if it is the credential and `at` is
    #         inside its valid hours (or it has none). Otherwise rule the holder out, with a
    #         reason naming the code (and its hours, when it has them).
    # TODO 3: if the credential is not an override code it is a badge: the row's holder could.
    # TODO 4: everyone in `alibis` with an alibi, who is not in `could`, is ruled out with the
    #         alibi as the reason. Anyone with no alibi who is not in `could` is not ruled out.
    raise NotImplementedError("TODO 1 to 4: the door check")

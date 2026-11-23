"""Chapter 09 exercise: the alibi check, done by code.

The chapter ends with the model reading two times and Python doing the arithmetic. Write that
check as a function: badge swipes against a camera log and a walking time, returning the gap and
whether the alibi holds. No model is needed: this is the part a model should not do.

Grade it with `make exercise N=09` (offline). Stuck? `make hint N=09`.
Start again? `make exercise-reset N=09`.
"""

from __future__ import annotations

import csv  # noqa: F401  (the solution uses it)
import io  # noqa: F401
from typing import Any


def seconds_of(t: str) -> int:
    """'23:31:02' -> seconds after midnight."""
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def check_alibi(
    badge_csv: str,
    camera_csv: str,
    *,
    holder: str,
    left_door: str,
    arrived_door: str,
    camera: str,
    walk_minutes: float,
    tolerance_minutes: float = 2.0,
    corroborate_within_s: int = 120,
) -> dict[str, Any]:
    """Test a walking alibi against the badge log and a camera log.

    Both logs are CSV text with a header row: the badge log has time, badge_id, holder, door,
    direction, result (case/badge-log.csv); the camera log has time, camera, event, detail
    (case/gate-camera-log.csv). Times are HH:MM:SS on one night.

    Returns a dict:
        left             time of the holder's first swipe out of `left_door`
        arrived          time of their first swipe at `arrived_door` after that
        camera_seen      first `camera` event at or after `arrived`, within corroborate_within_s
                         seconds; None if the camera saw nothing in that window
        corroborated     True when camera_seen is not None
        elapsed_minutes  minutes from left to arrived, rounded to one decimal
        gap_minutes      elapsed minus walk_minutes, rounded to one decimal
        holds            True when gap_minutes <= tolerance_minutes

    Raises ValueError when either swipe is missing.
    """
    # TODO 1: read the badge CSV (csv.DictReader over io.StringIO) and keep the holder's rows.
    # TODO 2: `left` is the first row at left_door with direction "out". None found: ValueError.
    # TODO 3: `arrived` is the first row at arrived_door strictly after `left` (not the swipe
    #         back in later that night). None found: ValueError.
    # TODO 4: read the camera CSV and find the first `camera` row from `arrived` to
    #         `arrived` + corroborate_within_s seconds.
    # TODO 5: elapsed and gap in minutes, rounded to one decimal; holds is gap <= tolerance.
    raise NotImplementedError("TODO 1 to 5: the alibi check")

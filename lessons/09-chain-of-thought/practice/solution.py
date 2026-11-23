"""Chapter 09 solution: the alibi check, done by code. Read it once you have tried."""

from __future__ import annotations

import csv
import io
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
    badges = list(csv.DictReader(io.StringIO(badge_csv)))
    mine = [r for r in badges if r["holder"] == holder]
    left = next((r["time"] for r in mine if r["door"] == left_door and r["direction"] == "out"),
                None)
    if left is None:
        raise ValueError(f"no swipe out of {left_door} for {holder}")
    arrived = next(
        (r["time"] for r in mine
         if r["door"] == arrived_door and seconds_of(r["time"]) > seconds_of(left)),
        None,
    )
    if arrived is None:
        raise ValueError(f"no swipe at {arrived_door} for {holder} after {left}")

    seen = None
    for r in csv.DictReader(io.StringIO(camera_csv)):
        after = seconds_of(r["time"]) - seconds_of(arrived)
        if r["camera"] == camera and 0 <= after <= corroborate_within_s:
            seen = r["time"]
            break

    elapsed = (seconds_of(arrived) - seconds_of(left)) / 60
    gap = round(elapsed - walk_minutes, 1)
    return {
        "left": left,
        "arrived": arrived,
        "camera_seen": seen,
        "corroborated": seen is not None,
        "elapsed_minutes": round(elapsed, 1),
        "gap_minutes": gap,
        "holds": gap <= tolerance_minutes,
    }

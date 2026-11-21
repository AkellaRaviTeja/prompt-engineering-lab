"""promptfoo assertion: the calibrated judge, refusing to grade if it is not calibrated.

    assert:
      - type: python
        metric: no_speculation
        value: file://judge/assert_no_speculation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge import JUDGE_MODEL, MIN_KAPPA, calibration, judge  # noqa: E402


def get_assert(output: str, context: dict) -> dict:
    cal = calibration()
    if not cal or cal.get("judge_model") != JUDGE_MODEL or cal.get("kappa", 0) < MIN_KAPPA:
        return {"pass": False, "score": 0,
                "reason": "judge not calibrated: run `make judge-calibrate` first"}
    under_test = (context or {}).get("provider", {}).get("label", "")
    if under_test.replace("-", ":") == JUDGE_MODEL.replace("-", ":"):
        return {"pass": False, "score": 0, "reason": "the judge may not grade its own model"}
    passed, reason = judge(output, context["vars"]["question"])
    return {"pass": passed, "score": 1 if passed else 0, "reason": f"judge {JUDGE_MODEL}: {reason}"}

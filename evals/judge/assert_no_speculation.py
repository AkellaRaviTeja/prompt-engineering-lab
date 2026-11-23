"""promptfoo assertion: the calibrated judge, refusing to grade if it is not calibrated.

    assert:
      - type: python
        metric: no_speculation
        value: file://judge/assert_no_speculation.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge import JUDGE_MODEL, MIN_KAPPA, calibration, judge, stale  # noqa: E402


def pin_to_calibrated_tier(cal: dict) -> None:
    """Run the judge on the tier it was calibrated on, whatever tier the models under test use.

    On the hosted eval (LANTERN_TIER=hosted), qwen3:4b would otherwise resolve to a hosted model
    that was never checked against the labels.
    """
    from lantern.config import load_config

    if os.environ.get("LANTERN_TIER") != cal.get("tier", "local"):
        os.environ["LANTERN_TIER"] = cal.get("tier", "local")
        load_config.cache_clear()


def grades_itself(context: dict | None) -> bool:
    """True when the model under test is the judge's model, by label, provider id or config."""
    provider = (context or {}).get("provider") or {}
    if isinstance(provider, str):
        provider = {"id": provider}
    names = [provider.get("label"), provider.get("id"),
             (provider.get("config") or {}).get("model")]
    judge_name = JUDGE_MODEL.replace("-", ":")
    return any(str(n).replace("-", ":").endswith(judge_name) for n in names if n)


def get_assert(output: str, context: dict) -> dict:
    cal = calibration()
    if not cal or cal.get("judge_model") != JUDGE_MODEL:
        return {"pass": False, "score": 0,
                "reason": "judge not calibrated: run `make judge-calibrate` first"}
    if cal.get("kappa", 0) < MIN_KAPPA:
        return {"pass": False, "score": 0,
                "reason": f"judge not usable: kappa {cal.get('kappa', 0):.2f} against the labels, "
                          f"{MIN_KAPPA} needed"}
    why = stale(cal)
    if why:
        return {"pass": False, "score": 0,
                "reason": f"judge calibration is stale: {why}; run `make judge-calibrate`"}
    if grades_itself(context):
        return {"pass": False, "score": 0, "reason": "the judge may not grade its own model"}
    pin_to_calibrated_tier(cal)
    passed, reason = judge(output, context["vars"]["question"])
    return {"pass": passed, "score": 1 if passed else 0, "reason": f"judge {JUDGE_MODEL}: {reason}"}

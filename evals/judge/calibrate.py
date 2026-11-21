"""Calibrate the no-speculation judge against labels written by a person.

    make judge-calibrate        # live: runs the judge on every labelled answer

Prints a confusion table, agreement, true-pass and true-fail rates and Cohen's kappa, and writes
`calibration.json`. The eval's assertion refuses to use a judge whose kappa is below MIN_KAPPA or
whose calibration was made for another model.

Labels: `labels.jsonl`, 24 synthetic answers, half that keep the rule and half that break it,
written and labelled by the lab's author. Several break it only by hinting ("the person with the
code"), which is where a weak judge fails.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge import CALIBRATION, HERE, JUDGE_MODEL, MIN_KAPPA, judge  # noqa: E402


def kappa(tp: int, fn: int, fp: int, tn: int) -> float:
    """Cohen's kappa for two raters on a pass/fail label: agreement beyond chance."""
    n = tp + fn + fp + tn
    if n == 0:
        return 0.0
    observed = (tp + tn) / n
    expected = ((tp + fn) * (tp + fp) + (fp + tn) * (fn + tn)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def score(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs of (label_pass, judge_pass) -> the calibration numbers."""
    tp = sum(lab and jud for lab, jud in pairs)
    fn = sum(lab and not jud for lab, jud in pairs)
    fp = sum(not lab and jud for lab, jud in pairs)
    tn = sum(not lab and not jud for lab, jud in pairs)
    n = len(pairs)
    return {
        "n": n,
        "agreement": (tp + tn) / n if n else 0.0,
        "true_pass_rate": tp / (tp + fn) if tp + fn else 0.0,
        "true_fail_rate": tn / (tn + fp) if tn + fp else 0.0,
        "kappa": kappa(tp, fn, fp, tn),
        "confusion": {"label_pass_judge_pass": tp, "label_pass_judge_fail": fn,
                      "label_fail_judge_pass": fp, "label_fail_judge_fail": tn},
    }


def main(model: str = JUDGE_MODEL) -> int:
    labels = [json.loads(x) for x in (HERE / "labels.jsonl").read_text().splitlines() if x]
    if not labels:
        print("calibrate: no labels found")
        return 1
    pairs, misses = [], []
    for item in labels:
        passed, reason = judge(item["answer"], item["question"], model=model)
        pairs.append((item["label"] == "pass", passed))
        if passed != (item["label"] == "pass"):
            misses.append(f"  {item['id']}: label {item['label']}, judge said "
                          f"{'pass' if passed else 'fail'} ({reason})")
    result = score(pairs)
    result.update({"judge_model": model, "tier": "local", "date": date.today().isoformat(),
                   "machine": f"{platform.system()} {platform.machine()}",
                   "min_kappa": MIN_KAPPA})
    print(f"calibrate: {model} on {result['n']} labelled answers")
    print(f"  agreement {result['agreement']:.2f}, true-pass {result['true_pass_rate']:.2f}, "
          f"true-fail {result['true_fail_rate']:.2f}, kappa {result['kappa']:.2f}")
    print("\n".join(misses) or "  no disagreements")
    if model == JUDGE_MODEL:
        CALIBRATION.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"  wrote {CALIBRATION.relative_to(HERE.parents[1])}")
    ok = result["kappa"] >= MIN_KAPPA
    print(f"calibrate: {'usable' if ok else 'NOT usable'} (kappa >= {MIN_KAPPA} needed)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))

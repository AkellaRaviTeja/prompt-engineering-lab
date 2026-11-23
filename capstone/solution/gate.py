"""The CI gate: a candidate prompt version must not score worse than the baseline.

    uv run python capstone/solution/gate.py classify-message --baseline v1 --candidate v2
    uv run python capstone/solution/gate.py extract-invoice --baseline v1 --candidate v1 \\
        --baseline-report base.json --candidate-report cand.json

Exit 0 when the candidate passes, 1 on a regression beyond the tolerance, 2 when the gate
cannot compare (no cases, different tasks, different golden sets). It prints every check.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import evaluate as ev
import golden

DEFAULT_TOLERANCE = 0.03  # one message case in 48 is 0.021: one flip passes, two fail


def incomparable(baseline: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    """Why two reports cannot be compared, or None when they can."""
    if baseline.get("task") != candidate.get("task"):
        return f"tasks differ: {baseline.get('task')} and {candidate.get('task')}"
    if not baseline.get("n") or not candidate.get("n"):
        return "a report has no cases: nothing was checked"
    base_ids = [c["id"] for c in baseline.get("cases", [])]
    cand_ids = [c["id"] for c in candidate.get("cases", [])]
    if base_ids != cand_ids:
        return "the reports ran on different golden cases"
    return None


def compare(
    baseline: dict[str, Any], candidate: dict[str, Any], tolerance: float = DEFAULT_TOLERANCE
) -> tuple[bool, list[str]]:
    """Every check the gate makes, and whether the candidate passes all of them."""
    problem = incomparable(baseline, candidate)
    if problem:
        return False, [f"FAIL {problem}"]
    lines: list[str] = []
    ok = True
    drop = baseline["score"] - candidate["score"]
    good = drop <= tolerance + 1e-9
    ok &= good
    lines.append(
        f"{'ok  ' if good else 'FAIL'} score {candidate['score']:.3f} "
        f"against baseline {baseline['score']:.3f} (tolerance {tolerance:.3f})"
    )
    rise = (candidate["invalid"] - baseline["invalid"]) / candidate["n"]
    good = rise <= tolerance + 1e-9
    ok &= good
    lines.append(
        f"{'ok  ' if good else 'FAIL'} invalid replies {candidate['invalid']} "
        f"against baseline {baseline['invalid']} of {candidate['n']}"
    )
    for name, base in baseline.get("fields", {}).items():
        cand = candidate.get("fields", {}).get(name, 0.0)
        good = base - cand <= tolerance + 1e-9
        ok &= good
        lines.append(f"{'ok  ' if good else 'FAIL'} field {name} {cand:.3f} against {base:.3f}")
    newly_failed = [
        b["id"] for b, c in zip(baseline["cases"], candidate["cases"], strict=True)
        if b["passed"] and not c["passed"]
    ]
    if newly_failed:
        lines.append(f"note cases the baseline passed and the candidate fails: "
                     f"{', '.join(newly_failed)}")
    return ok, lines


def main(argv: list[str] | None = None, chat: Callable[..., Any] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("task")
    p.add_argument("--baseline", required=True, help="baseline prompt version, e.g. v1")
    p.add_argument("--candidate", required=True, help="candidate prompt version, e.g. v2")
    p.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    p.add_argument("--baseline-report", type=Path, help="a saved report instead of a run")
    p.add_argument("--candidate-report", type=Path, help="a saved report instead of a run")
    p.add_argument("--limit", type=int, help="only the first N golden cases")
    p.add_argument("--out", type=Path, help="save the reports from a run in this folder")
    a = p.parse_args(argv)

    cases = None

    def report(version: str, path: Path | None) -> dict[str, Any]:
        nonlocal cases
        if path:
            return ev.load(path)
        if cases is None:
            cases = golden.build(a.task)[: a.limit] if a.limit else golden.build(a.task)
        print(f"gate: running {a.task}@{version} on {len(cases)} cases", flush=True)
        r = ev.evaluate(a.task, version, cases, chat=chat)
        if a.out:
            ev.save(r, a.out / f"{a.task}@{version}.json")
        return r

    base = report(a.baseline, a.baseline_report)
    cand = report(a.candidate, a.candidate_report)
    print(f"gate: {a.task} {base.get('version')} (baseline) against "
          f"{cand.get('version')} (candidate), {cand.get('n', 0)} cases")
    problem = incomparable(base, cand)
    if problem:
        print(f"gate: cannot compare: {problem}")
        return 2
    ok, lines = compare(base, cand, a.tolerance)
    for line in lines:
        print("  " + line)
    print("gate: PASS" if ok else "gate: FAIL, the candidate regressed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

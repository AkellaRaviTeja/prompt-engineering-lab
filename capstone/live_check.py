"""Run the capstone pipeline live on the golden set and check it against recorded thresholds.

    make capstone-live                      # your capstone/work/, local tier
    make capstone-live ARGS=--solution      # the reference in capstone/solution/
    make capstone-live TIER=hosted          # the hosted model (needs a key and `--extra cloud`)

For each task in thresholds.yaml it runs your eval at the listed prompt version through the real
`lantern.chat`, saves the report under .progress/capstone/, and fails when the score is below
the recorded minimum or more replies were invalid than the recorded maximum.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

import yaml

from lantern import chat
from lantern.config import model_name, tier

CAPSTONE = Path(__file__).resolve().parent
ROOT = CAPSTONE.parent


def load(folder: Path, name: str):
    if not (folder / f"{name}.py").exists():
        raise SystemExit(f"capstone-live: {folder.relative_to(ROOT)}/{name}.py does not exist yet."
                         " Build it first (make capstone grades it offline).")
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    return importlib.import_module(name)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--solution", action="store_true", help="run capstone/solution/")
    p.add_argument("--task", help="only this task")
    a = p.parse_args()

    who = "solution" if a.solution else "work"
    folder = CAPSTONE / who
    golden, evaluate = load(folder, "golden"), load(folder, "evaluate")
    level = tier()
    recorded = yaml.safe_load((CAPSTONE / "thresholds.yaml").read_text(encoding="utf-8"))
    limits = recorded.get(level)
    tasks = recorded["tasks"]
    if a.task:
        tasks = {a.task: tasks[a.task]}
    print(f"capstone-live: {who}/ on the {level} tier, model {model_name(None)}")

    calls = 0

    def counted(messages, **kwargs):
        nonlocal calls
        calls += 1
        print(".", end="", flush=True)
        return chat(messages, **kwargs)

    failures = 0
    for task, version in tasks.items():
        cases = golden.build(task)
        print(f"\n{task}@{version}: {len(cases)} cases ", end="", flush=True)
        start = time.perf_counter()
        r = evaluate.evaluate(task, version, cases, chat=counted)
        seconds = time.perf_counter() - start
        out = ROOT / ".progress" / "capstone" / who / f"{task}@{version}.json"
        evaluate.save(r, out)
        fields = ", ".join(f"{k} {v:.3f}" for k, v in r["fields"].items())
        print(f"\n  score {r['score']:.3f} ({r['passed']}/{r['n']}), invalid {r['invalid']}, "
              f"calls {r['calls']}, {seconds:.0f}s")
        print(f"  fields: {fields}")
        failed = [c["id"] for c in r["cases"] if not c["passed"]]
        print(f"  failed cases: {', '.join(failed) or 'none'}")
        print(f"  report: {out.relative_to(ROOT)}")
        if not limits:
            continue
        t = limits[task]
        ok_score = r["score"] >= t["min_score"]
        ok_invalid = r["invalid"] <= t["max_invalid"]
        print(f"  {'ok  ' if ok_score else 'FAIL'} score {r['score']:.3f} >= {t['min_score']}")
        print(f"  {'ok  ' if ok_invalid else 'FAIL'} invalid {r['invalid']} <= {t['max_invalid']}")
        failures += (not ok_score) + (not ok_invalid)

    if not limits:
        print(f"\ncapstone-live: no thresholds are recorded for the {level} tier, nothing to check")
        return 2
    print(f"\ncapstone-live: {'PASS' if not failures else f'FAIL, {failures} check(s) missed'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

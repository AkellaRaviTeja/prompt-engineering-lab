"""make hosted-check: one chapter end to end on the hosted tier, live, then checked.

Needs a key (ANTHROPIC_API_KEY in .env, or the key for LANTERN_HOSTED_PROVIDER). Runs chapter 08
with TIER=hosted and RECORD=1, so the run is also saved to recordings/hosted/ for learners
without a key, then checks:

- the chapter finished, and recorded its numbers as 08-hosted;
- every call it made went to the hosted provider, with input and output tokens and a cost
  computed from a checked price (none unknown, none zero);
- the chapter's own thresholds (THRESHOLDS below) hold on the hosted model.

Cost: chapter 08 makes about a dozen short calls; on claude-haiku-5-5 that is well under one US
cent at the prices in config.yaml. The script prints the exact total.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lantern import calllog  # noqa: E402
from lantern.config import load_config  # noqa: E402

CHAPTER = "08"
# Thresholds on chapter 08's recorded metrics (lessons/08-*/run.py learn.record).
THRESHOLDS = {"valid_invoices": ("==", "invoices"), "northwind_invoices": ("==", 3)}


def main() -> int:
    cfg = load_config()
    provider = os.getenv("LANTERN_HOSTED_PROVIDER") or cfg["hosted"]["provider"]
    key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
           "gemini": "GEMINI_API_KEY"}[provider]
    if not os.getenv(key):
        print(f"hosted-check: not run, {key} is not set (add it to .env)")
        return 1
    log = Path(tempfile.mkdtemp()) / "calls.jsonl"
    env = {**os.environ, "LANTERN_TIER": "hosted", "LANTERN_RECORD": "1",
           "LANTERN_CALL_LOG": str(log)}
    lesson = next((ROOT / "lessons").glob(f"{CHAPTER}-*"))
    rec = ROOT / "recordings" / "hosted" / f"{CHAPTER}.jsonl"
    rec.unlink(missing_ok=True)  # a fresh recording, not one appended to an old one
    r = subprocess.run([sys.executable, str(lesson / "run.py"), "--no-predict"], cwd=ROOT, env=env)
    problems = []
    if r.returncode:
        problems.append(f"chapter {CHAPTER} exited with {r.returncode}")
    calls = calllog.read(log)
    if not calls:
        problems.append("no calls were logged")
    total = 0.0
    for c in calls:
        if c["gen_ai.provider.name"] != provider:
            problems.append(f"a call went to {c['gen_ai.provider.name']}, not {provider}")
        if not c["gen_ai.usage.input_tokens"] or not c["gen_ai.usage.output_tokens"]:
            problems.append(f"a call recorded no tokens: {c}")
        if not c["lantern.cost_usd"]:
            problems.append(f"no cost (unknown or zero price): {c['gen_ai.request.model']}")
        total += c["lantern.cost_usd"] or 0.0
    res_path = ROOT / ".progress" / "results" / f"{CHAPTER}-hosted.json"
    metrics = json.loads(res_path.read_text())["metrics"] if res_path.exists() else {}
    if not metrics:
        problems.append("the chapter recorded no hosted results")
    for name, (op, want) in THRESHOLDS.items():
        want = metrics.get(want, want) if isinstance(want, str) else want
        have = metrics.get(name)
        if have is None or not {"==": have == want, ">=": have >= want}[op]:
            problems.append(f"{name}: {have!r} (want {op} {want!r})")
    print(f"hosted-check: chapter {CHAPTER} on {provider}, {len(calls)} calls, "
          f"{sum(c['gen_ai.usage.input_tokens'] for c in calls)} input tokens "
          f"({sum(c['gen_ai.usage.cache_read.input_tokens'] for c in calls)} cached), "
          f"{sum(c['gen_ai.usage.output_tokens'] for c in calls)} output, "
          f"cost USD {total:.6f}")
    print("\n".join(problems) or "hosted-check: passed; the run is saved in recordings/hosted/")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

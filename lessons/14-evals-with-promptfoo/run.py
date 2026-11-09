"""Chapter 14: run the promptfoo eval suite against LANTERN's models and summarise it."""

import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

from lantern import load_config
from lantern.config import ROOT
from lantern.ui import (
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    save_shot,
    step,
    your_turn,
)

chapter("14", "Proven, not demonstrated", """
The case conference is in nine days. Everything LANTERN has produced so far will be put in front
of Marcus Hale, and Hale has already said what he will ask: which instructions, which model, which
settings, and can you reproduce it. A demonstration answers none of that. A demonstration is the
one run that happened to work. Varma wants a test suite: every prompt, on every model, against
every piece of evidence with a known right answer, run the same way every time.
""")

EVALS = ROOT / "evals"
PROMPTFOO = ["npx", "--yes", "promptfoo@0.124.1"]

step("1. The suite is a config file")
config = (EVALS / "promptfooconfig.yaml").read_text(encoding="utf-8")
evidence("evals/promptfooconfig.yaml", "\n".join(
    line for line in config.splitlines() if line.strip() and not line.lstrip().startswith("#")))
note("prompts x providers x tests: each test names the prompts it applies to.")

step("2. Tests are generated from the evidence")
build = subprocess.run([sys.executable, str(EVALS / "build_tests.py")], capture_output=True,
                       text=True, check=True)
note(build.stdout.strip())
sample = (EVALS / "tests" / "extraction.yaml").read_text(encoding="utf-8").split("- description")
evidence("evals/tests/extraction.yaml (first test)", "- description" + sample[1])
note("Expected totals come from the seized ledger, case/ledger.csv: the record we must verify.")

step("3. promptfoo eval")
summary_file = EVALS / "output" / "eval-summary.txt"
if "--reuse" in sys.argv and summary_file.exists():
    note("--reuse: showing the last run instead of running the eval again.")
    header, *summary = summary_file.read_text(encoding="utf-8").splitlines()
else:
    env = {**os.environ, "OLLAMA_BASE_URL": load_config()["ollama"]["host"],
           "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1"}
    note("Running 70 cells one at a time on CPU. This takes 15 minutes or more.")
    start = time.perf_counter()
    run = subprocess.run([*PROMPTFOO, "eval", "--no-cache", "--no-table", "--no-progress-bar",
                          "-c", "promptfooconfig.yaml", "--output", "output/results.json"],
                         cwd=EVALS, env=env, capture_output=True, text=True)
    minutes = (time.perf_counter() - start) / 60
    summary = [line for line in re.sub(r"\x1b\[[0-9;]*m", "", run.stdout).splitlines()
               if line.strip()][-18:]
    header = f"promptfoo eval (exit code {run.returncode}, {minutes:.1f} min)"
    summary_file.write_text("\n".join([header, *summary]) + "\n", encoding="utf-8")
evidence(header, "\n".join(summary))
note("Exit code 100 means the run finished and some tests failed. That is a result, not a crash.")

step("4. The matrix: pass rate per model and prompt")
data = json.loads((EVALS / "output" / "results.json").read_text(encoding="utf-8"))
cells = defaultdict(lambda: [0, 0])
for r in data["results"]["results"]:
    key = (r["provider"].get("label") or r["provider"]["id"], r["prompt"]["label"])
    cells[key][0] += bool(r["success"])
    cells[key][1] += 1
providers = sorted({k[0] for k in cells})
prompts = sorted({k[1] for k in cells})
table = Table(title="Tests passed (passed / run)")
table.add_column("prompt")
for p in providers:
    table.add_column(p, justify="right")
for prompt in prompts:
    row = [prompt]
    for p in providers:
        ok, n = cells[(p, prompt)]
        colour = "green" if ok == n else "yellow" if ok >= n / 2 else "red"
        row.append(f"[{colour}]{ok}/{n}[/{colour}]")
    table.add_row(*row)
console.print(table)
stats = data["results"]["stats"]
note(f"Overall: {stats['successes']} passed, {stats['failures']} failed, "
     f"{stats.get('errors', 0)} errors.")
note("Open the full results with `make eval-view` (http://localhost:15500).")

your_turn(
    "14",
    check=[
        "In the matrix, compare classify-v1 with classify-v2 on the same model. Then open "
        "evals/prompts/classify-v1.json and evals/prompts/classify-v2.json. Which lines could "
        "explain the gap?",
        "Find the extract-invoice cells that failed. Run make eval-view, filter to failures, and "
        "compare the two models' outputs for that test.",
        "Open evals/tests/rules.yaml. Which assertion is graded by a model instead of by code, "
        "and would you trust it on its own?",
    ],
    exercises=[
        "In evals/promptfooconfig.yaml, under `providers:`, add `- id: ollama:chat:qwen3:4b` "
        "with `label: qwen3-4b` and `config: *settings`. Compare the extra minutes with the "
        "extra passes.",
        "Add finance to the label list in evals/prompts/classify-v1.json and "
        "evals/prompts/classify-v2.json. In `classification_tests()` in evals/build_tests.py, "
        "add a test whose `label` var is finance. What does v1 do with it?",
        "In `extraction_tests()` in evals/build_tests.py, replace the `total_matches_ledger` "
        "javascript assert with an llm-rubric whose value is 'The total matches "
        "{{ledger_total}}.' Compare the run time and the grader's mistakes.",
        "In evals/tests/extraction.yaml, delete `prompts:` and `- extract-invoice` from the "
        "extract NW-0402 test. Run make eval (this lesson rebuilds that file), then make "
        "eval-view and read what the classify prompts made of it.",
    ],
)

finding("""
The suite runs end to end and every result is stored with its prompt, model, settings and
output. Hale can have all of it. The rules hold on both models. Extraction is nearly perfect. The
terse classifier fails every test it is given, and the better one still misses the quietest
threats. And one extraction test fails on both models in exactly the same way.

Varma looks at the matrix for a long time. "Before you fix anything, find out what is failing.
A failing test is evidence too."
""")
save_shot("14-evals-with-promptfoo")

"""Chapter 18: run the promptfoo eval suite against LANTERN's models and summarise it."""

import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

import yaml

from lantern import learn, load_config
from lantern.config import ROOT, tier
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

chapter("18", "Proven, not demonstrated", """
The case conference is in nine days. Everything LANTERN has produced so far will be put in front
of Marcus Hale, and Hale has already said what he will ask: which instructions, which model, which
settings, and can you reproduce it. A demonstration answers none of that. A demonstration is the
one run that happened to work. Varma wants a test suite: every prompt, on every model, against
every piece of evidence with a known right answer, run the same way every time.
""")

EVALS = ROOT / "evals"
PROMPTFOO = ["npx", "--yes", "promptfoo@0.124.1"]
# The hosted tier runs the same tests through lantern.chat on the hosted model, into its own
# output files, so a hosted run never overwrites the committed local results.
HOSTED = tier() == "hosted"
CONFIG = "promptfooconfig.hosted.yaml" if HOSTED else "promptfooconfig.yaml"
SUFFIX = ".hosted" if HOSTED else ""

step("1. The suite is a config file")
config = (EVALS / CONFIG).read_text(encoding="utf-8")
evidence(f"evals/{CONFIG}", "\n".join(
    line for line in config.splitlines() if line.strip() and not line.lstrip().startswith("#")))
note("prompts x providers x tests: each test names the prompts it applies to.")

step("2. Tests are generated from the evidence")
build = subprocess.run([sys.executable, str(EVALS / "build_tests.py")], capture_output=True,
                       text=True, check=True)
note(build.stdout.strip())
sample = (EVALS / "tests" / "extraction.yaml").read_text(encoding="utf-8").split("- description")
evidence("evals/tests/extraction.yaml (first test)", "- description" + sample[1])
note("Expected totals come from the seized ledger, case/ledger.csv: the record we must verify.")

tests_now = sum(len(yaml.safe_load((EVALS / "tests" / f).read_text(encoding="utf-8")))
                for f in ("extraction.yaml", "classification.yaml", "rules.yaml"))

step("3. promptfoo eval")
summary_file = EVALS / "output" / f"eval-summary{SUFFIX}.txt"
results_file = EVALS / "output" / f"results{SUFFIX}.json"
reused = "--reuse" in sys.argv and summary_file.exists() and results_file.exists()
minutes = None
p_pass = learn.predict_number("How many cells will pass? (The unchanged suite has 70.)",
                              unit="cells")
if HOSTED and "--reuse" in sys.argv and not reused:
    # No hosted eval has been recorded: say so, and read the local run rather than invent one.
    note("--reuse on the hosted tier: no hosted eval has been recorded (not run). Showing the "
         "local run instead; `make lesson N=18 TIER=hosted` with a key records one.")
    summary_file = EVALS / "output" / "eval-summary.txt"
    results_file = EVALS / "output" / "results.json"
    reused = True
if reused:
    note("--reuse: showing the last run instead of running the eval again.")
    header, *summary = summary_file.read_text(encoding="utf-8").splitlines()
else:
    env = {**os.environ, "OLLAMA_BASE_URL": load_config()["ollama"]["host"],
           "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1"}
    # The Python provider and the judge need lantern: run them with this interpreter.
    env.setdefault("PROMPTFOO_PYTHON", sys.executable)
    note("Running 70 cells one at a time on CPU, plus the judge. This takes several minutes.")
    start = time.perf_counter()
    run = subprocess.run([*PROMPTFOO, "eval", "--no-cache", "--no-table", "--no-progress-bar",
                          "-c", CONFIG, "--output", f"output/results{SUFFIX}.json"],
                         cwd=EVALS, env=env, capture_output=True, text=True)
    minutes = (time.perf_counter() - start) / 60
    summary = [line for line in re.sub(r"\x1b\[[0-9;]*m", "", run.stdout).splitlines()
               if line.strip()][-18:]
    header = f"promptfoo eval (exit code {run.returncode}, {minutes:.1f} min)"
    summary_file.write_text("\n".join([header, *summary]) + "\n", encoding="utf-8")
    # results.json is committed: take this machine's home directory out of it.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "clean_eval_output.py")],
                   capture_output=True, text=True)
evidence(header, "\n".join(summary))
note("Exit code 100 means the run finished and some tests failed. That is a result, not a crash.")
data = json.loads(results_file.read_text(encoding="utf-8"))
rows = data["results"]["results"]
passed_cells = sum(bool(r["success"]) for r in rows)
learn.reveal(p_pass, actual=passed_cells, tolerance=0.2,
             why=f"{passed_cells} of {len(rows)} passed. A pass rate is a property of the prompts, "
                 "the models and the tests together: the same prompts against harder tests would "
                 "score lower. Step 4 shows where the failures sit.")

step("4. The matrix: pass rate per model and prompt")
cells = defaultdict(lambda: [0, 0])
for r in rows:
    key = (r["provider"].get("label") or r["provider"]["id"], r["prompt"]["label"])
    cells[key][0] += bool(r["success"])
    cells[key][1] += 1
providers = sorted({k[0] for k in cells})
prompts = sorted({k[1] for k in cells})
p_low = learn.predict("Which prompt will pass the smallest share of its tests, over both models?",
                      prompts)
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
by_prompt = {pr: [sum(cells[(p, pr)][i] for p in providers) for i in (0, 1)] for pr in prompts}
lowest = min(prompts, key=lambda pr: by_prompt[pr][0] / max(by_prompt[pr][1], 1))
learn.reveal(p_low, answer=prompts.index(lowest),
             why=f"{lowest} passed {by_prompt[lowest][0]} of {by_prompt[lowest][1]}. Same models, "
                 "same settings: when one prompt fails where another passes on the same tests, "
                 "the prompt is the cause. Compare classify-v1 with classify-v2.")
stats = data["results"]["stats"]
note(f"Overall: {stats['successes']} passed, {stats['failures']} failed, "
     f"{stats.get('errors', 0)} errors.")
note("Open the full results with `make eval-view` (http://localhost:15500).")

step("5. Who grades the grader: the calibrated judge")
cal_path = EVALS / "judge" / "calibration.json"
cal = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else None
if cal:
    c = cal["confusion"]
    table = Table(title=f"{cal['judge_model']} against {cal['n']} answers a person labelled "
                        f"({cal['date']}, {cal['tier']}, {cal['machine']})")
    table.add_column("")
    table.add_column("judge: pass", justify="right")
    table.add_column("judge: fail", justify="right")
    table.add_row("label: pass", str(c["label_pass_judge_pass"]), str(c["label_pass_judge_fail"]))
    table.add_row("label: fail", str(c["label_fail_judge_pass"]), str(c["label_fail_judge_fail"]))
    console.print(table)
    usable = cal["kappa"] >= cal["min_kappa"]
    note(f"Agreement {cal['agreement']:.2f}, true-pass rate {cal['true_pass_rate']:.2f}, "
         f"true-fail rate {cal['true_fail_rate']:.2f}, Cohen's kappa {cal['kappa']:.2f} "
         f"({cal['min_kappa']} needed): "
         + ("[green]usable[/green]." if usable else "[red]NOT usable: it fails closed[/red]."))
else:
    usable = False
    note("[red]No evals/judge/calibration.json: the judge has not been checked against the "
         "labels, so every no_speculation cell fails closed. Run `make judge-calibrate`.[/red]")
verdicts = []
for r in rows:
    for comp in (r.get("gradingResult") or {}).get("componentResults") or []:
        if (comp.get("assertion") or {}).get("metric") == "no_speculation":
            verdicts.append((r["provider"].get("label") or r["provider"]["id"],
                             bool(comp.get("pass")), comp.get("reason") or ""))
judged = [v for v in verdicts if v[2].startswith("judge ")]
refused_self = sum("its own model" in v[2] for v in verdicts)
p_judge = learn.predict(
    "Asked 'Who pushed Mr Reyes down the stairs?', how many of the models under test will the "
    "judge pass?", ["all of them", "some of them", "none of them"])
for prov, ok, reason in verdicts:
    note(f"no_speculation, {prov}: {'pass' if ok else '[red]fail[/red]'} ({reason[:110]})")
judge_passed = sum(v[1] for v in verdicts)
learn.reveal(p_judge, answer=0 if verdicts and judge_passed == len(verdicts) else
             2 if judge_passed == 0 else 1,
             why="A judge is a model grading a model. Its verdict is only worth what its "
                 "agreement with a person is worth, which is why it is calibrated against labels "
                 "first and is never the model under test: a model grading itself shares its own "
                 "blind spots.")

your_turn(
    "18",
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

learn.record(
    cells=len(rows),
    passed=passed_cells,
    failed=len(rows) - passed_cells,
    pass_rate=round(passed_cells / max(len(rows), 1), 3),
    providers=len(providers),
    tests=tests_now,
    extract_passed=by_prompt.get("extract-invoice", [0, 0])[0],
    classify_v1_passed=by_prompt.get("classify-v1", [0, 0])[0],
    classify_v2_passed=by_prompt.get("classify-v2", [0, 0])[0],
    rules_passed=by_prompt.get("evidence-rules", [0, 0])[0],
    judge_kappa=round(cal["kappa"], 3) if cal else None,
    judge_agreement=round(cal["agreement"], 3) if cal else None,
    judge_usable=usable,
    judge_graded=len(judged),
    judge_refused_self=refused_self,
    minutes=round(minutes, 1) if minutes is not None else None,
    reused=reused,
)

finding("""
The suite runs end to end and every result is stored with its prompt, model, settings and
output. Hale can have all of it. The rules hold on both models. Extraction is nearly perfect. The
terse classifier fails every test it is given, and the better one still misses the quietest
threats. And one extraction test fails on both models in exactly the same way.

Varma looks at the matrix for a long time. "Before you fix anything, find out what is failing.
A failing test is evidence too."
""")
save_shot("18-evals-with-promptfoo")

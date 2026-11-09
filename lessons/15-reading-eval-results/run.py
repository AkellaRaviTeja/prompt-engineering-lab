"""Chapter 15: read the eval results, triage the failures, and follow the one that is not a bug."""

import json
from collections import defaultdict

from lantern import case, chat
from lantern.config import ROOT
from lantern.ui import (
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    reply,
    save_shot,
    step,
    your_turn,
)

chapter("15", "The test that would not pass", """
It is past midnight and the EOW is empty except for you and the hum of LANTERN. The eval results
are open on the screen. You have fixed prompts all evening, and the pass rate has climbed. One
test has not moved. It fails on the small model, it fails on the medium model, and it fails with
the same number every time. You stop trying to fix the prompt and start reading the evidence.
""")

results_path = ROOT / "evals" / "output" / "results.json"
if not results_path.exists():
    raise SystemExit("No eval results yet. Run `make eval` (or `make lesson N=14`) first.")
data = json.loads(results_path.read_text(encoding="utf-8"))["results"]
rows = data["results"]

step("1. Start with the headline, then distrust it")
passed = sum(bool(r["success"]) for r in rows)
note(f"{passed}/{len(rows)} cells passed ({passed / len(rows):.0%}). A single number hides "
     "which tests, which models and which prompts.")

step("2. Break it down: which assertion failed, where")
by_metric = defaultdict(lambda: [0, 0])
for r in rows:
    for c in (r.get("gradingResult") or {}).get("componentResults") or []:
        metric = (c.get("assertion") or {}).get("metric") or (c.get("assertion") or {}).get("type")
        by_metric[metric][0] += bool(c.get("pass"))
        by_metric[metric][1] += 1
table = Table(title="Assertions passed, by named metric")
table.add_column("metric")
table.add_column("passed", justify="right")
for metric, (ok, n) in sorted(by_metric.items()):
    table.add_row(metric, f"{ok}/{n}")
console.print(table)

step("3. Compare prompts on the same tests")
prompt_scores = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for r in rows:
    label = r["prompt"]["label"]
    if label.startswith("classify"):
        prov = r["provider"].get("label") or r["provider"]["id"]
        prompt_scores[label][prov][0] += bool(r["success"])
        prompt_scores[label][prov][1] += 1
for label, provs in sorted(prompt_scores.items()):
    scores = ", ".join(f"{p}: {ok}/{n}" for p, (ok, n) in sorted(provs.items()))
    note(f"{label}: {scores}")
note("Same model, same tests, different prompt: the gap between v1 and v2 is the prompt's work.")

step("4. Group failures by test: what fails everywhere, and how?")


def answer(r: dict) -> str:
    """The part of an output the test cares about, normalised so equal answers compare equal."""
    out = ((r.get("response") or {}).get("output") or "").strip()
    try:
        return f"total={json.loads(out.replace('```json', '').replace('```', ''))['total']}"
    except (ValueError, KeyError, TypeError):
        return "".join(c for c in out.lower() if c.isalpha())[:24]


failing = defaultdict(list)
cells_per_test = defaultdict(int)
for r in rows:
    desc = r["testCase"]["description"]
    cells_per_test[desc] += 1
    if not r["success"]:
        failing[desc].append(answer(r))
table = Table(title="Failing tests")
table.add_column("test")
table.add_column("failed in")
table.add_column("pattern")
for desc, answers in sorted(failing.items(), key=lambda kv: -len(kv[1])):
    if len(answers) < cells_per_test[desc]:
        pattern = "some cells"
    elif len(set(answers)) == 1:
        pattern = f"[red]every cell, same answer ({answers[0]})[/red]"
    else:
        pattern = f"every cell, {len(set(answers))} different answers"
    table.add_row(desc, f"{len(answers)}/{cells_per_test[desc]}", pattern)
console.print(table)
note("Some cells: a prompt or a model problem. Every cell with different answers: the task is "
     "hard, or the gold label is debatable. Every cell with the SAME answer: suspect the "
     "expected value.")
note("The four threats that fail everywhere are the quiet ones ('Stairwell C. 23:30.'). Whether "
     "they are threats is a human judgement, made with context the model does not have.")

step("5. Read one failure in full: extract NW-0419")
for r in rows:
    if r["testCase"]["description"] == "extract NW-0419":
        prov = r["provider"].get("label") or r["provider"]["id"]
        output = (r.get("response") or {}).get("output", "")
        note(f"{prov}: output {output.strip()[:120]}")
note("Expected (from the seized ledger): total 9400.00")
evidence("case/invoices/NW-0419.txt", case.read("invoices/NW-0419.txt"))
ledger_row = next(r for r in case.rows("ledger.csv") if r["reference"] == "NW-0419")
evidence("case/ledger.csv, row NW-0419", ", ".join(f"{k}={v}" for k, v in ledger_row.items()))
note("Every model read 94,000.00 from the invoice. The models are right. The test expects the "
     "ledger, and the ledger says 9,400.00.")

step("6. Bad prompt, bad test, or bad data?")
note("Not a bad prompt: both models give the same total, and it matches the document.")
note("Not a bad assertion: the code compares numbers correctly; every other invoice passes.")
note("Bad data: the reference record itself disagrees with its source. Ask why.")

audit = case.read("evidence-store-audit.csv")
personnel = case.read("personnel-note.md")
evidence("case/evidence-store-audit.csv", audit)
r = chat(
    "Using only the evidence below, answer in at most four short bullet points: who changed "
    "the ledger after it was seized, when, which row and field, and what the HR record says "
    "about that account. Quote timestamps exactly. If something is not in the evidence, say "
    "'not in evidence'.\n\n"
    f"<audit_log>\n{audit}\n</audit_log>\n\n<hr_record>\n{personnel}\n</hr_record>",
    temperature=0, max_tokens=300,
)
reply("LANTERN reads the audit log", r.text, meta="temperature 0, standing orders applied")

step("7. Check LANTERN against the log, line by line")
modify = next(line for line in audit.splitlines() if ",modify," in line)
note(f"The only 'modify' line: {modify.split(',')[0]} by {modify.split(',')[1]}.")
if modify.split(",")[0].split()[1] not in r.text:
    note("[red]LANTERN's timestamp does not match that line.[/red] It took a time from a "
         "neighbouring row. Quote-checking catches what fluency hides.")
note("An account is not a person. The log shows the pk.dsouza login was used. It does not "
     "show who typed the password. LANTERN's wording blurs that; your report must not.")

your_turn(
    "15",
    check=[
        "In the metric table, which metric is furthest from full marks, and which prompt do its "
        "tests use?",
        "In the failing-tests table, find the row marked 'every cell, same answer'. Compare that "
        "answer with case/invoices/NW-0419.txt and the case/ledger.csv row above. Which one "
        "disagrees with the others?",
        "Check LANTERN's audit-log reply against case/evidence-store-audit.csv. Is each timestamp "
        "on the line it describes? Does the log show a person, or a login?",
    ],
    exercises=[
        "No edit: run make eval-view, open http://localhost:15500 and set the display filter to "
        "failures only. Sort each failure into the three patterns in the table above.",
        "Write evals/prompts/classify-v3.json that fixes one v1-only failure. Add it under "
        "`prompts:` in evals/promptfooconfig.yaml with `label: classify-v3`, add classify-v3 to "
        "the `prompts` list in `classification_tests()` in evals/build_tests.py, then run make "
        "lesson N=14 and this lesson. Did anything else break?",
        "In `extraction_tests()` in evals/build_tests.py, set `total = 94000.0` when `ref` is "
        "NW-0419, instead of the ledger's `amount_kbd`. Run make lesson N=14, then this lesson. "
        "What has the suite stopped telling you?",
        "No edit: open case/evidence-store-audit.csv and read every line, not only the 'modify' "
        "one. What else in it should worry you?",
    ],
)

finding("""
The ledger was seized on 31 March. At 02:47 on 3 April, an account called pk.dsouza changed one
field in one row: the amount on Northwind invoice NW-0419, from 94,000.00 to 9,400.00. The
account belongs to a detective sergeant who retired three years ago. It had not been used since.
Someone with access to the EOW evidence store made the biggest Northwind payment look small.

Case File 01 is closed with its question answered. Tomas Reyes did not fall by accident. At
23:36 someone opened the bottom door of stairwell C from the outside, using an audit override
code that Brightwater and Co had been given and never handed back. Raj Malhotra's sixteen
minutes do not add up. Three invoices paid a company with no ships into an account in Port Sabran.

Varma reads the audit line twice, then closes the door of her office before she speaks. "Nobody
outside this room hears about this. Not the duty sergeant, not headquarters. Tomorrow we start
on the archive: twenty years of Halcyon's records, and every one of them has been in a building
that someone inside this one can reach."

Case File 02 begins in the archive.
""")
save_shot("15-reading-eval-results")

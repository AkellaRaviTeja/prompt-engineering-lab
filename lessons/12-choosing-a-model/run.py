"""Chapter 12: measure LANTERN's three models on the same tasks before trusting any of them."""

import json
import math
import time

import httpx

from lantern import case, chat, learn, load_config
from lantern.config import ROOT, model_name, tier
from lantern.ui import Table, chapter, console, finding, note, save_shot, step, your_turn

chapter("12", "Three models, one case", """
Varma has a rule about tools: you do not trust one you have not tested. LANTERN carries three
models of the same family, a small one, a medium one and a large one. Okafor wants the large one
for everything. The duty sergeant wants answers before the morning briefing. Hale wants to know,
in writing, why you chose the one you chose. You set up a fair test: the same sixteen messages
from Reyes's phone, the same invoice, the same settings, and a stopwatch.
""")

cfg = load_config()
HOST = cfg["ollama"]["host"]
MODELS = [cfg["models"]["small"], cfg["models"]["default"], cfg["models"]["large"]]

# A balanced, fixed subset: the first 6 threats, 5 logistics and 5 personal messages.
messages = case.jsonl("messages.jsonl")
subset = []
for label, n in (("threat", 6), ("logistics", 5), ("personal", 5)):
    subset += [m for m in messages if m["label"] == label][:n]

CLASSIFY = """Classify one text message from the work phone of a murdered company CFO.

Labels:
- threat: pressures, intimidates or warns the CFO, or tries to stop his inquiry
- logistics: ordinary business operations (ships, fuel, invoices, maintenance, schedules)
- personal: family, friends, health, private life

Reply as JSON: {{"label": "threat" | "logistics" | "personal"}}

<message from="{sender}">{text}</message>"""

# Structured output pins the answer to three allowed values, so a model that likes to
# "think out loud" (qwen3:4b does, even with think off) cannot ramble past the token budget.
LABEL_SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": ["threat", "logistics", "personal"]}},
    "required": ["label"],
}

INVOICE_SCHEMA = {
    "type": "object",
    "properties": {"invoice_id": {"type": "string"}, "vendor": {"type": "string"},
                   "total": {"type": "number"}},
    "required": ["invoice_id", "vendor", "total"],
}
invoice = case.read("invoices/NW-0402.txt")


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: the smallest value with at least q% of the values at or below."""
    ordered = sorted(values)
    return ordered[max(math.ceil(q / 100 * len(ordered)), 1) - 1]


def scorecard(rows: list[dict]) -> list[dict]:
    """Per model: accuracy, p50 and p95 latency, cost per correct answer. practice/ builds this."""
    out = []
    for model in dict.fromkeys(r["model"] for r in rows):
        mine = [r for r in rows if r["model"] == model]
        right = sum(r["correct"] for r in mine)
        costs = [r["cost_usd"] for r in mine]
        unknown = any(c is None for c in costs)
        out.append({
            "model": model,
            "n": len(mine),
            "accuracy": right / len(mine),
            "p50_s": percentile([r["seconds"] for r in mine], 50),
            "p95_s": percentile([r["seconds"] for r in mine], 95),
            "cost_per_correct": None if unknown or not right else sum(costs) / right,
        })
    return out


def resident_size(model: str) -> float:
    """Load the model and read its size straight away (another job may evict it later)."""
    for _ in range(3):
        chat("ok", model=model, max_tokens=1, temperature=0)
        if size := loaded_size(model):
            return size
    return 0.0


def loaded_size(model: str) -> float:
    """Memory the loaded model occupies, in GB, from Ollama's /api/ps."""
    for m in httpx.get(f"{HOST}/api/ps", timeout=10).json().get("models", []):
        if m["name"] == model:
            return m["size"] / 1e9
    return 0.0


note("The classification prompt is the `CLASSIFY` variable in run.py. `LABEL_SCHEMA` pins "
     "the answer to three labels.")

HOSTED = tier() == "hosted"
if HOSTED:
    note("Hosted tier: the three aliases map to " + ", ".join(model_name(m) for m in MODELS)
         + ". Memory and cold start are Ollama's: a hosted provider does not expose the memory "
         "a model occupies, and there is no model to load, so those columns read n/a.")

p_best = learn.predict("Which model will classify the most of the sixteen messages correctly?",
                       ["the small one", "the medium one", "the large one", "a tie at the top"])
p_extract = learn.predict(
    "Invoice NW-0402 to JSON: will the small model put every field in the right place?",
    ["yes", "no"])
p_p50 = None

results, timed = [], []
for model in MODELS:
    step(f"Testing {model}")
    if model == MODELS[-1] and results:
        p_p50 = learn.predict_number(
            f"The medium model took {results[-1]['p50_s']:.2f} s per message at the median. "
            f"How long will {model} take?", unit="seconds")
    start = time.perf_counter()
    chat("Reply with: ready", model=model, max_tokens=5, temperature=0)
    load_s = time.perf_counter() - start
    note(f"cold start (load into memory + first answer): {load_s:.1f} s")

    if HOSTED:
        memory = None  # a hosted provider does not report it
    else:
        memory = resident_size(model)
    correct, rows, wrong = 0, [], []
    for m in subset:
        r = chat(CLASSIFY.format(sender=m["from"], text=m["text"]), model=model,
                 temperature=0, max_tokens=20, format=LABEL_SCHEMA)
        try:
            guess = r.json()["label"]
        except (json.JSONDecodeError, KeyError, TypeError):
            guess = r.text[:20]
        rows.append({"model": model, "correct": guess == m["label"], "seconds": r.seconds,
                     "cost_usd": r.cost_usd})
        if guess == m["label"]:
            correct += 1
        else:
            wrong.append(f"{m['id']} expected {m['label']}, got {guess[:20]!r}")
    timed += rows
    card = scorecard(rows)[0]
    note(f"classification: {correct}/{len(subset)} correct")
    for w in wrong[:4]:
        note(f"  miss: {w}")

    r = chat(f"Extract the invoice fields.\n<invoice>\n{invoice}\n</invoice>", model=model,
             format=INVOICE_SCHEMA, temperature=0, max_tokens=120)
    try:
        data = r.json()
        extract_ok = data.get("invoice_id") == "NW-0402" and abs(data["total"] - 71200) < 0.01
    except (json.JSONDecodeError, KeyError, TypeError):
        data, extract_ok = r.text, False
    note(f"extraction: {data} -> {'correct' if extract_ok else 'WRONG'}")

    r = chat("In about 80 words, describe what a forensic accountant does.", model=model,
             temperature=0, max_tokens=120)
    results.append({
        "model": model_name(model) if HOSTED else model,
        "accuracy": card["accuracy"],
        "extraction_ok": extract_ok,
        "p50_s": card["p50_s"],
        "p95_s": card["p95_s"],
        "cost_per_correct": card["cost_per_correct"],
        "tokens_per_s": r.tokens_per_second,
        "memory_gb": memory,
        "cold_start_s": load_s,
    })
    if model == MODELS[0]:
        learn.reveal(p_extract, answer=0 if extract_ok else 1,
                     why="Classifying and extracting are different skills. A model can pick the "
                     "right label from three and still put a vendor's name in the invoice_id "
                     "field. One task is not enough to rank models.")
    if p_p50 is not None and model == MODELS[-1]:
        learn.reveal(p_p50, actual=round(card["p50_s"], 2), tolerance=0.3,
                     why="Every message pays for reading the prompt and writing the answer, and "
                     "a larger model does both more slowly. The median hides the slowest call; "
                     "p95 shows it.")

step("The scorecard")
table = Table(title="Same tasks, same settings, temperature 0, latency on the wall clock")
for col in ("model", "classify (16)", "extract", "p50/msg", "p95/msg", "tokens/s", "memory",
            "cold start", "cost/correct"):
    table.add_column(col, justify="right" if col != "model" else "left")
for r in results:
    cost = "n/a" if r["cost_per_correct"] is None else f"${r['cost_per_correct']:.6f}"
    table.add_row(r["model"], f"{r['accuracy']:.0%}", "yes" if r["extraction_ok"] else "no",
                  f"{r['p50_s']:.2f} s", f"{r['p95_s']:.2f} s", f"{r['tokens_per_s']:.1f}",
                  "n/a" if r["memory_gb"] is None else f"{r['memory_gb']:.1f} GB",
                  "n/a" if HOSTED else f"{r['cold_start_s']:.1f} s", cost)
console.print(table)
top = max(r["accuracy"] for r in results)
leaders = [i for i, r in enumerate(results) if r["accuracy"] == top]
learn.reveal(p_best, answer=leaders[0] if len(leaders) == 1 else 3,
             why="On sixteen messages one message is six points of accuracy, so a tie or a "
             "one-message lead is common. Read the misses before you read the percentage.")

if HOSTED:
    note("Hosted run: the local scorecard in docs/charts is left as it is.")
else:
    out = ROOT / "docs" / "charts" / "12-model-scorecard.json"
    out.write_text(json.dumps(results, indent=2))
    note(f"raw numbers saved to {out.relative_to(ROOT)}")
    try:
        from chart import draw  # noqa: E402  (lesson-local helper, needs matplotlib)

        note(f"chart saved to {draw(results).relative_to(ROOT)}")
    except ImportError:
        note("matplotlib not installed; skipping the chart (uv sync installs it).")

note("p50 and p95 are wall clock per message: prompt processing, generation and any model load.")
note("Read the table as a trade: each row down buys accuracy with time and memory.")
note("Your numbers will differ on a GPU. The method is the lesson, not the figures.")

small, medium, large = results
learn.record(
    accuracy_small=round(small["accuracy"], 4),
    accuracy_medium=round(medium["accuracy"], 4),
    accuracy_large=round(large["accuracy"], 4),
    p50_s_small=round(small["p50_s"], 3),
    p50_s_medium=round(medium["p50_s"], 3),
    p50_s_large=round(large["p50_s"], 3),
    p95_s_small=round(small["p95_s"], 3),
    p95_s_medium=round(medium["p95_s"], 3),
    p95_s_large=round(large["p95_s"], 3),
    p95_over_p50_large=round(large["p95_s"] / large["p50_s"], 2) if large["p50_s"] else None,
    extract_ok_small=small["extraction_ok"],
    extract_ok_medium=medium["extraction_ok"],
    extract_ok_large=large["extraction_ok"],
    tokens_per_s_small=round(small["tokens_per_s"], 1),
    tokens_per_s_medium=round(medium["tokens_per_s"], 1),
    tokens_per_s_large=round(large["tokens_per_s"], 1),
    cold_start_s_large=round(large["cold_start_s"], 2),
    cost_per_correct_small=small["cost_per_correct"],
    cost_per_correct_large=large["cost_per_correct"],
    hosted=HOSTED,
)
best = max(results, key=lambda r: r["accuracy"])
ratio = (f"{best['p50_s'] / medium['p50_s']:.1f}x" if medium["p50_s"]
         else "an unmeasured multiple of")
memory = "an unreported amount" if best["memory_gb"] is None else f"{best['memory_gb']:.1f} GB"
small_extract = ("also extracts the invoice correctly" if small["extraction_ok"]
                 else "cannot reliably copy an invoice number into the right field")
your_turn(
    "12",
    check=[
        "Read the scorecard row by row. Where does accuracy go up, and what does each step to a "
        "bigger model cost in latency, memory and cold start?",
        "Compare each model's 'extraction:' line with case/invoices/NW-0402.txt. Is every value "
        "in the field it belongs in?",
        "Read the 'miss:' lines for all three models and look the ids up in "
        "case/messages.jsonl. Are the misses spread across labels, or do they cluster?",
    ],
    exercises=[
        "Pull a fourth model (ollama pull llama3.2:3b) and add \"llama3.2:3b\" to `MODELS` in "
        "run.py. Also change `small, medium, large = results` to `small, medium, large, *extra = "
        "results`, and add a fourth colour to `colours` in "
        "lessons/12-choosing-a-model/chart.py.",
        "Run make lesson N=12 TIER=hosted (ANTHROPIC_API_KEY in .env). Memory and cold start "
        "read n/a; compare classify, p50, p95 and cost/correct with your local run.",
        "In run.py, delete `format=LABEL_SCHEMA` from the classification chat call and change "
        "the `Reply as JSON` line in `CLASSIFY` to 'Reply with one word: threat, logistics or "
        "personal.' What happens to qwen3:4b?",
        "No edit: run make lesson N=12 twice. After each run, git diff "
        "docs/charts/12-model-scorecard.json shows which numbers moved.",
    ],
)

finding(f"""
On these sixteen messages the small model scores {small['accuracy']:.0%}, the medium
{medium['accuracy']:.0%} and the large {large['accuracy']:.0%}. The small model
{small_extract}.
The most accurate, {best['model']}, costs {ratio} the medium model's median time per message
and {memory} of memory, on a machine that runs everything else in the building. None of them
sorts threats well enough to go unsupervised.

You write the policy down for Hale: the medium model for bulk triage, the large one for findings
that go to court, and a person reads every message marked as a threat. Model, version, settings,
test and score are in the file. Varma signs it. "Now make sure it still holds when they change
the models."
""")
save_shot("12-choosing-a-model")

"""Chapter 12: measure LANTERN's three models on the same tasks before trusting any of them."""

import json
import time

import httpx

from lantern import case, chat, load_config
from lantern.config import ROOT
from lantern.ui import Table, chapter, console, finding, note, save_shot, step

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


def server_seconds(r) -> float:
    """Ollama's own timing for one call, minus model loading: what the model itself cost."""
    return (r.raw.get("total_duration", 0) - r.raw.get("load_duration", 0)) / 1e9


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


results = []
for model in MODELS:
    step(f"Testing {model}")
    start = time.perf_counter()
    chat("Reply with: ready", model=model, max_tokens=5, temperature=0)
    load_s = time.perf_counter() - start
    note(f"cold start (load into memory + first answer): {load_s:.1f} s")

    memory = resident_size(model)
    correct, latencies, wrong = 0, [], []
    for m in subset:
        r = chat(CLASSIFY.format(sender=m["from"], text=m["text"]), model=model,
                 temperature=0, max_tokens=20, format=LABEL_SCHEMA)
        latencies.append(server_seconds(r))
        try:
            guess = r.json()["label"]
        except (json.JSONDecodeError, KeyError, TypeError):
            guess = r.text[:20]
        if guess == m["label"]:
            correct += 1
        else:
            wrong.append(f"{m['id']} expected {m['label']}, got {guess[:20]!r}")
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
        "model": model,
        "accuracy": correct / len(subset),
        "extraction_ok": extract_ok,
        "latency_s": sum(latencies) / len(latencies),
        "tokens_per_s": r.tokens_per_second,
        "memory_gb": memory,
        "cold_start_s": load_s,
    })

step("The scorecard")
table = Table(title="Same tasks, same settings, temperature 0, CPU only")
for col in ("model", "classify (16)", "extract", "latency/msg", "tokens/s", "memory",
            "cold start"):
    table.add_column(col, justify="right" if col != "model" else "left")
for r in results:
    table.add_row(r["model"], f"{r['accuracy']:.0%}", "yes" if r["extraction_ok"] else "no",
                  f"{r['latency_s']:.2f} s", f"{r['tokens_per_s']:.1f}",
                  f"{r['memory_gb']:.1f} GB", f"{r['cold_start_s']:.1f} s")
console.print(table)

out = ROOT / "docs" / "charts" / "12-model-scorecard.json"
out.write_text(json.dumps(results, indent=2))
note(f"raw numbers saved to {out.relative_to(ROOT)}")
try:
    from chart import draw  # noqa: E402  (lesson-local helper, needs matplotlib)

    note(f"chart saved to {draw(results).relative_to(ROOT)}")
except ImportError:
    note("matplotlib not installed; skipping the chart (uv sync installs it).")

note("latency/msg is Ollama's own timing per message, excluding model load and queueing.")
note("Read the table as a trade: each row down buys accuracy with time and memory.")
note("Your numbers will differ on a GPU. The method is the lesson, not the figures.")

small, medium, large = results
best = max(results, key=lambda r: r["accuracy"])
small_extract = ("also extracts the invoice correctly" if small["extraction_ok"]
                 else "cannot reliably copy an invoice number into the right field")
finding(f"""
On these sixteen messages the small model scores {small['accuracy']:.0%}, the medium
{medium['accuracy']:.0%} and the large {large['accuracy']:.0%}. The small model
{small_extract}.
The most accurate, {best['model']}, costs {best['latency_s'] / medium['latency_s']:.1f}x the medium
model's time per message and {best['memory_gb']:.1f} GB of memory, on a machine that runs
everything else in the building. None of them sorts threats well enough to go unsupervised.

You write the policy down for Hale: the medium model for bulk triage, the large one for findings
that go to court, and a person reads every message marked as a threat. Model, version, settings,
test and score are in the file. Varma signs it. "Now make sure it still holds when they change
the models."
""")
save_shot("12-choosing-a-model")

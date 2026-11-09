"""Chapter 13: a prompt tuned to one model against a prompt written as a contract."""

import json
import re
from pathlib import Path

from lantern import case, chat, load_config
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

chapter("13", "The swap", """
A memo from headquarters: next quarter every analysis workstation in the force moves to a new
model family. Nobody can tell you which one yet. Varma reads it and asks one question. "Will the
findings we have already filed still reproduce on the new machine?" You open the prompt folder.
The first Northwind prompt you wrote is still there, written in a hurry on the night the
envelope arrived. It worked once. You never checked whether it works twice.
""")

HERE = Path(__file__).parent
EXPECTED = {"NW-0388": 62500.0, "NW-0402": 71200.0, "NW-0419": 94000.0}
SCHEMA = {
    "type": "array",
    "items": {"type": "object",
              "properties": {"invoice_id": {"type": "string"}, "total": {"type": "number"}},
              "required": ["invoice_id", "total"]},
}


def load_prompt(name: str) -> tuple[dict, str]:
    """A prompt file is YAML-style front matter plus a template body."""
    text = (HERE / "prompts" / name).read_text(encoding="utf-8")
    _, meta, body = text.split("---", 2)
    fields = dict(line.split(": ", 1) for line in meta.strip().splitlines())
    return fields, body.strip()


def parse_v1(text: str) -> dict[str, float]:
    """The parser written for v1's output: 'NW-0388 ... 62,500.00' on one line."""
    found = {}
    for line in text.splitlines():
        m = re.search(r"(NW-\d{4}).*?(\d{1,3}(?:,\d{3})+\.\d{2})", line)
        if m:
            found[m.group(1)] = float(m.group(2).replace(",", ""))
    return found


def parse_v2(text: str) -> dict[str, float]:
    try:
        return {row["invoice_id"]: float(row["total"]) for row in json.loads(text)}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {}


invoices = "\n\n".join(case.read(f"invoices/{n}.txt") for n in
                       ("NW-0388", "GTS-1182", "NW-0402", "HCS-0554", "NW-0419"))
evidence("five invoices from Reyes's mailbox (3 from Northwind)", invoices[:600] + "\n...")

meta1, v1 = load_prompt("v1.md")
meta2, v2 = load_prompt("v2.md")
step("1. The two versions")
reply(f"v{meta1['version']} ({meta1['status']}, written for {meta1['written_for']})", v1,
      style="red")
reply(f"v{meta2['version']} ({meta2['status']}, written for {meta2['written_for']})", v2,
      style="green")

cfg = load_config()["models"]
today, tomorrow = cfg["default"], cfg["small"]
note(f"'Today' is {today}. To simulate the swap, 'tomorrow' is {tomorrow}: a different model "
     "that nobody tuned these prompts for.")

rows = []
for model in (today, tomorrow):
    for version, template, parser, fmt in (("v1", v1, parse_v1, None),
                                           ("v2", v2, parse_v2, SCHEMA)):
        step(f"2. {version} on {model}")
        r = chat(template.format(invoices=invoices), model=model, temperature=0,
                 max_tokens=400, format=fmt)
        reply(f"{version} on {model}", r.text[:900], meta=f"{r.output_tokens} tokens")
        got = parser(r.text)
        exact = sum(got.get(k) == v for k, v in EXPECTED.items())
        wrong = sorted(set(got) - set(EXPECTED))
        rows.append((model, version, len(got) > 0, f"{exact}/3", ", ".join(wrong) or "none"))

step("3. Did the findings survive the swap?")
table = Table(title="Northwind payments: parsed by code, checked against the invoices")
for col in ("model", "prompt", "parsed?", "exact totals", "rows that should not be there"):
    table.add_column(col)
for model, version, parsed, exact, extra in rows:
    table.add_row(model, version, "yes" if parsed else "[red]no[/red]", exact, extra)
console.print(table)

note("v1's output is prose shaped by one model's habits. Its parser is a guess about those habits.")
note("v2 states a contract (schema, rules, delimiters) that any capable model can meet.")
note("A contract makes failures visible, not impossible: watch for extra rows on the small model.")
note("The changelog in prompts/CHANGELOG.md records why each line changed. Read it.")
note("What protects you on swap day is not the prompt. It is the eval that proves the prompt.")

your_turn(
    "13",
    check=[
        "Compare the 'parsed?' column with the v1 replies above. Is v1's answer wrong, or only in "
        "a shape that `parse_v1` in run.py cannot read?",
        "Read the 'rows that should not be there' column. Open those invoices in case/invoices/ "
        "and check who issued each one.",
        "Open lessons/13-future-proofing/prompts/v1.md, v2.md and CHANGELOG.md side by side. "
        "Which v1 lines were removed, and what reason does the changelog give?",
    ],
    exercises=[
        "Copy prompts/v2.md to prompts/v3.md, set `version: 3`, add the rule \"vendor must be "
        "exactly 'Northwind Freight Ltd'\" and a v3 entry in prompts/CHANGELOG.md. In run.py, add "
        "a `vendor` string to `SCHEMA`, load v3 with `load_prompt` and add a v3 row to the loop.",
        "Set `provider: anthropic` (or openai, gemini) in config.yaml, with the key in .env and "
        "`uv sync --extra cloud`. Both models then become the cloud model. Do v1 and v2 parse?",
        "In run.py, change the regex in `parse_v1` so it also reads v1's bullet lines. Run it "
        "again tomorrow. Does your fix still match?",
        "Add /no_think to the start of the body in prompts/v2.md, after the front matter. Do the "
        "qwen3:1.7b rows change? What would another model family make of it?",
    ],
)

finding("""
The three Northwind invoices total 227,700.00 KBD, each dated inside one of Malhotra's trips to
Port Sabran. The contract-style prompt reports all three on both models in a form code can check.
The hurried version produced prose that its own parser could not read, even on the model it was
written for. And on the smaller model the contract was met in shape but broken in substance: it
listed suppliers that are not Northwind. Only a test would have caught that.

Varma initials the changelog. "Before anything goes to Hale, I want this proven on every model we
might use. Not demonstrated. Proven."
""")
save_shot("13-future-proofing")

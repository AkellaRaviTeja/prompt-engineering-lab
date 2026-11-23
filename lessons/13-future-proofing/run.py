"""Chapter 13: a prompt tuned to one model against a prompt written as a contract."""

import json
import re
import string
from pathlib import Path

from lantern import case, chat, learn, load_config
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

p_v1 = learn.predict(
    f"v1 was written for {today} and its parser was written for v1's answers. Will that parser "
    f"read v1's answer on {today}?", ["yes", "no"])
p_v2 = learn.predict(
    f"On {tomorrow}, which nobody tuned these prompts for, how many of the three Northwind totals "
    "will v2 get exactly right?", ["0", "1", "2", "3"])

rows, replies, measured = [], {}, {}
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
        who = "today" if model == today else "tomorrow"
        replies[version, who] = r.text
        measured[version, who] = {"parsed": len(got) > 0, "exact": exact, "extra": len(wrong)}
        if (version, who) == ("v1", "today"):
            learn.reveal(p_v1, answer=0 if got else 1,
                         why="A parser written against one answer is a guess about a habit. "
                         "\"A nice list\" leaves the shape to the model, and the shape moves "
                         "from run to run, even on the model the prompt was tuned for.")
        if (version, who) == ("v2", "tomorrow"):
            learn.reveal(p_v2, answer=exact,
                         why="v2 states the task, the rules and the output schema, so any capable "
                         "model can meet it. Whether the rows are the right ones is a separate "
                         "question: count the rows that should not be there.")

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

step("4. The contract, checked by code")
MODEL_SPECIFIC = ("/no_think", "/think", "<|im_start|>", "<|im_end|>", "[INST]")
CONTRACT = {"fields": {"invoice_id": "string", "total": "number"},
            "id_field": "invoice_id", "id_pattern": r"^[A-Z]{2,4}-\d{4}$"}


def render(template: str, variables: dict[str, str]) -> str:
    """Fill a prompt template; refuse model-specific tokens and missing or unused variables."""
    for token in MODEL_SPECIFIC:
        if token in template:
            raise ValueError(f"model-specific token {token!r} in the template")
    names = {f for _, f, _, _ in string.Formatter().parse(template) if f}
    if names - set(variables) or set(variables) - names:
        raise ValueError(f"template needs {sorted(names)}, got {sorted(variables)}")
    return template.format(**variables)


def validate(text: str, contract: dict, *, source: str) -> list[str]:
    """What is wrong with a reply under the contract. [] means it meets it. practice/ builds it."""
    try:
        data = json.loads(text)
    except ValueError:
        return ["not JSON: prose, a code fence or a thinking block around the data"]
    if not isinstance(data, list):
        return ["not a JSON list"]
    kinds = {"string": str, "number": (int, float)}
    problems, seen = [], set()
    for i, row in enumerate(data):
        if not isinstance(row, dict) or set(row) != set(contract["fields"]):
            problems.append(f"row {i}: fields must be exactly {sorted(contract['fields'])}")
            continue
        for name, kind in contract["fields"].items():
            if isinstance(row[name], bool) or not isinstance(row[name], kinds[kind]):
                problems.append(f"row {i}: {name} must be a {kind}")
        rid = str(row[contract["id_field"]])
        if not re.match(contract["id_pattern"], rid):
            problems.append(f"row {i}: {rid!r} does not match {contract['id_pattern']}")
        elif rid not in source:
            problems.append(f"row {i}: {rid} is not in the material")
        if rid in seen:
            problems.append(f"row {i}: {rid} appears twice")
        seen.add(rid)
    return problems


p_meet = learn.predict("Of the four replies, how many meet the contract, checked by code?",
                       ["0", "1", "2", "3", "4"])
for label, template in (("v1", v1), ("v2", v2)):
    try:
        render(template, {"invoices": invoices})
        note(f"render() accepts {label}.")
    except ValueError as e:
        note(f"render() refuses {label}: {e}.")
contract = Table(title="Each reply against the contract")
for col in ("model", "prompt", "meets the contract?", "first problem"):
    contract.add_column(col)
passes = 0
for (version, who), text in replies.items():
    problems = validate(text, CONTRACT, source=invoices)
    passes += not problems
    measured[version, who]["contract"] = not problems
    contract.add_row(today if who == "today" else tomorrow, version,
                     "yes" if not problems else "[red]no[/red]", problems[0] if problems else "")
console.print(contract)
learn.reveal(p_meet, answer=passes,
             why="The contract checks shape, types and that every id exists in the material. It "
             "does not check that a row is a Northwind invoice: that is substance, and only the "
             "expected totals in step 3 test it.")

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
        "Run make lesson N=13 TIER=hosted (ANTHROPIC_API_KEY in .env). Both 'today' and "
        "'tomorrow' become the hosted model. Do v1 and v2 parse, and meet the contract?",
        "In run.py, change the regex in `parse_v1` so it also reads v1's bullet lines. Run it "
        "again tomorrow. Does your fix still match?",
        "Add /no_think to the start of the body in prompts/v2.md, after the front matter. Do the "
        "qwen3:1.7b rows change? What would another model family make of it?",
    ],
)

learn.record(
    v1_today_parsed=measured["v1", "today"]["parsed"],
    v1_today_exact=measured["v1", "today"]["exact"],
    v2_today_exact=measured["v2", "today"]["exact"],
    v2_today_extra=measured["v2", "today"]["extra"],
    v1_tomorrow_parsed=measured["v1", "tomorrow"]["parsed"],
    v1_tomorrow_exact=measured["v1", "tomorrow"]["exact"],
    v2_tomorrow_exact=measured["v2", "tomorrow"]["exact"],
    v2_tomorrow_extra=measured["v2", "tomorrow"]["extra"],
    v1_contract=measured["v1", "today"]["contract"] and measured["v1", "tomorrow"]["contract"],
    v2_contract=measured["v2", "today"]["contract"] and measured["v2", "tomorrow"]["contract"],
    contract_passes=passes,
)

v2_lines = []
for who, name in (("today", today), ("tomorrow", tomorrow)):
    m = measured["v2", who]
    others = (f" and listed {m['extra']} supplier(s) that are not Northwind"
              if m["extra"] else "")
    if not m["contract"]:
        v2_lines.append(f"On {name} the contract-style prompt broke the contract{others}.")
    elif m["extra"]:
        v2_lines.append(f"On {name} it met the contract in shape but listed {m['extra']} "
                        "supplier(s) that are not Northwind: wrong in substance.")
    else:
        v2_lines.append(f"On {name} it met the contract and listed only Northwind.")
v1_note = ("The hurried version produced prose its own parser could not read, even on the model "
           "it was written for." if not measured["v1", "today"]["parsed"] else
           "The hurried version happened to parse today; nothing in it promises it will tomorrow.")
finding(f"""
The three Northwind invoices total 227,700.00 KBD, each dated inside one of Malhotra's trips to
Port Sabran. {v1_note} {" ".join(v2_lines)} Only a test would have caught that.

Varma initials the changelog. "Before anything goes to Hale, I want this proven on every model we
might use. Not demonstrated. Proven."
""")
save_shot("13-future-proofing")

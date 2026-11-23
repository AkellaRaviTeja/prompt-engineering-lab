"""Chapter 08: turn invoices into validated JSON rows, then cross them with travel records."""

import json
import time
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from lantern import case, chat, learn
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

chapter("08", "Rows for the link chart", """
Okafor's office wall is covered in paper: vendors, bank accounts, names, arrows. He wants it in a
spreadsheet by morning. "Eight invoices from Reyes's mailbox," he says. "Every field, every
number, same shape every time. If one amount comes back as a sentence, the chart is useless."
""")


class Invoice(BaseModel):
    """One supplier invoice. Field order matters: the model fills them top to bottom."""

    invoice_id: str = Field(description="The invoice number exactly as printed, e.g. GTS-1182")
    vendor: str = Field(description="Supplier company name, in normal capitalisation")
    invoice_date: date = Field(description="Invoice date as YYYY-MM-DD")
    category: Literal["fuel", "marine services", "equipment hire", "it", "cleaning",
                      "freight coordination", "other"]
    service: str = Field(description="What was supplied, copied from the description line")
    total_kbd: float = Field(description="Total due as a plain number, no commas or currency")
    vat_number: str | None = Field(description="VAT registration, or null if none is printed")
    remit_to: str = Field(description="Bank account and bank name for payment")


invoices = case.files("invoices")
sample = case.read("invoices/NW-0419.txt")
evidence("invoices/NW-0419.txt", sample)

# With --mine, extraction is yours: practice/exercise.py extract(), with its own retry and cap.
MINE = learn.mine()

p_nice = learn.predict("Asked nicely for JSON, with no schema: will the reply pass validation?",
                       ["yes", "no"])
step("1. Asking nicely: 'Return JSON'")
ask = f"""Extract the invoice fields as JSON with keys invoice_id, vendor, invoice_date,
category, service, total_kbd, vat_number, remit_to.

{sample}"""
r = chat(ask, temperature=0, max_tokens=400)
reply("LANTERN, no schema", "```text\n" + r.text + "\n```",
      meta=f"{r.output_tokens} tokens")
try:
    Invoice.model_validate_json(r.text)
    no_schema_valid = True
    note("It parsed and validated this time. Asking nicely sometimes works.")
except ValidationError as e:
    no_schema_valid = False
    note(f"Failed validation with {e.error_count()} error(s). First: {e.errors()[0]['msg']}")
    note("Typical causes: a ```json fence, '94,000.00' as a string, a made-up category.")
learn.reveal(p_nice, answer=0 if no_schema_valid else 1,
             why="Without a schema the model writes what JSON usually looks like in its training "
                 "data: a friendly sentence, a fence, numbers with commas. Nothing stops it.")

step("2. Constrained decoding: pass the schema as `format`")
schema = Invoice.model_json_schema()
reply("Schema sent to Ollama (abridged)", "```json\n" + json.dumps(
    {k: schema["properties"][k] for k in ("category", "total_kbd", "vat_number")},
    indent=2) + "\n```", style="blue")
note("Ollama turns the schema into a grammar. Tokens that would break it get zero probability.")


def extract(text: str, retries: int = 2) -> tuple[Invoice | None, int]:
    """Constrained extraction with validation. On failure, show the model its error and retry."""
    messages = [{"role": "user", "content": f"Extract this invoice.\n\n{text}"}]
    for attempt in range(1, retries + 2):
        r = chat(messages, format=schema, temperature=0, max_tokens=400)
        try:
            return Invoice.model_validate_json(r.text), attempt
        except ValidationError as e:
            messages += [{"role": "assistant", "content": r.text},
                         {"role": "user", "content": f"That failed validation: {e}. Fix it."}]
    return None, retries + 1


p_calls = learn.predict(f"With the schema and up to two retries each, how many model calls for "
                        f"{len(invoices)} invoices?",
                        [f"{len(invoices)}: every one valid first time",
                         f"{len(invoices) + 1} to {len(invoices) + 4}",
                         f"more than {len(invoices) + 4}"])
if MINE:
    def extract(text: str) -> tuple[Invoice | None, int]:  # noqa: F811  (yours, with --mine)
        return MINE.extract(text, chat=chat, model_cls=Invoice, max_attempts=3)

rows: list[Invoice] = []
start = time.perf_counter()
attempts_used = 0
for path in invoices:
    inv, attempts = extract(path.read_text())
    attempts_used += attempts
    if inv:
        rows.append(inv)
    else:
        note(f"{path.name}: still invalid after retries, flagged for a human")
note(f"{len(rows)}/{len(invoices)} invoices valid, {attempts_used} calls in total, "
     f"{time.perf_counter() - start:.0f}s")

t = Table(title="Extracted invoices (validated by Pydantic)")
for col in ("invoice_id", "vendor", "date", "category", "total_kbd", "vat"):
    t.add_column(col, justify="right" if col == "total_kbd" else "left")
for inv in rows:
    t.add_row(inv.invoice_id, inv.vendor, str(inv.invoice_date), inv.category,
              f"{inv.total_kbd:,.2f}", inv.vat_number or "[red]none[/red]")
console.print(t)
learn.reveal(p_calls, answer=learn.bucket(attempts_used, [len(invoices), len(invoices) + 4]),
             why=f"{attempts_used} calls. The schema becomes a grammar (or the provider's native "
                 "structured output), so a token that would break it cannot be chosen: shape "
                 "failures mostly disappear, and the retry is left for rules a grammar cannot "
                 "express.")

p_source = learn.predict("Every row passed validation. How many fields will the check against "
                         "the printed invoices flag?", ["none", "1 to 3", "4 or more"])
step("3. Check the machine against the paper")
problems = 0
for inv in rows:
    printed = next(p for p in invoices if p.stem == inv.invoice_id).read_text()
    if f"{inv.total_kbd:,.2f}" not in printed:
        problems += 1
        note(f"{inv.invoice_id}: total {inv.total_kbd:,.2f} does not appear on the invoice")
    vat_line = next((ln for ln in printed.splitlines() if ln.startswith("VAT registration:")), "")
    if inv.vat_number and inv.vat_number not in vat_line:
        problems += 1
        note(f"{inv.invoice_id}: vat_number '{inv.vat_number}' is not a VAT number on the invoice "
             "(there is no VAT line). Corrected to null.")
        inv.vat_number = None
note(f"{problems} field(s) contradicted the source documents out of {len(rows)} invoices checked.")
note("Valid JSON is not the same as correct JSON. The schema guarantees shape, not truth.")
note("Categories need a human eye too: is a network switch 'it' or 'equipment hire'?")
learn.reveal(p_source, answer=learn.bucket(problems, [0, 3]),
             why="A schema guarantees the shape and the types. It cannot know that a bank "
                 "account is not a VAT number; only a check against the source can.")

p_trips = learn.predict("How many of the Northwind invoices fall inside one of Malhotra's trips?",
                        ["none", "some", "all of them"])

step("4. Cross the Northwind rows with Malhotra's travel")
trips = case.rows("malhotra-travel.csv")
nw = [inv for inv in rows if "northwind" in inv.vendor.lower()]
x = Table(title="Northwind invoices against R. Malhotra's approved travel")
for col in ("invoice", "date", "amount", "Malhotra was in", "trip"):
    x.add_column(col)
in_trips = 0
for inv in nw:
    trip = next((tr for tr in trips if date.fromisoformat(tr["depart"]) <= inv.invoice_date
                 <= date.fromisoformat(tr["return"])), None)
    in_trips += trip is not None
    x.add_row(inv.invoice_id, str(inv.invoice_date), f"{inv.total_kbd:,.2f}",
              trip["destination"] if trip else "Kestrel Bay",
              f"{trip['depart']} to {trip['return']}" if trip else "")
console.print(x)
note("The join is ordinary Python. The model only had to produce rows a program can trust.")
learn.reveal(p_trips, answer=0 if in_trips == 0 else (2 if in_trips == len(nw) else 1),
             why=f"{in_trips} of {len(nw)}. The model extracted; a date comparison in code made "
                 "the link, exactly and the same way every time.")

learn.record(
    no_schema_valid=no_schema_valid,
    invoices=len(invoices),
    valid_rows=len(rows),
    flagged=len(invoices) - len(rows),
    calls_total=attempts_used,
    retries_used=attempts_used - len(invoices),
    source_problems=problems,
    northwind_rows=len(nw),
    northwind_in_trips=in_trips,
    mine=bool(MINE),
)

your_turn(
    "08",
    check=[
        "Look at the first character of the no-schema reply. Why did validation reject it?",
        "Open case/invoices/NW-0419.txt and compare it with its row in the table. Is the vendor in "
        "normal capitalisation? Is every category the one you would pick?",
        "Read the step 3 notes. Which field had to be corrected, and what had the model put there?",
    ],
    exercises=[
        "In run.py, in `Invoice`, change `total_kbd` to plain `total_kbd: float` with no "
        "description. What type and format come back?",
        "In run.py, in extract(), change `format=schema` to `format=\"json\"` (JSON mode). "
        "Which fields drift?",
        "In run.py, move the `category` line to the top of `Invoice`, above `invoice_id`. "
        "Do the categories get worse?",
        "In run.py, change the `vat_number` description to \"Only the value printed after 'VAT "
        "registration:'. null if that line is absent.\" Does the source check still find problems?",
    ],
)

finding(f"""
{len(nw)} Northwind invoices, KBD {sum(i.total_kbd for i in nw):,.2f} in total. None carries a VAT
number. All of them remit to the same account at Sabran Mercantile Bank. And every one is dated
while Raj Malhotra was in Port Sabran on travel approved by Elena Voss.

Okafor pins a new card to the centre of his wall and draws three lines to it. "Operations does not
approve freight invoices," he says. "So why is every one of these coded to his cost centre?"
""")
save_shot("08-structured-output")

"""Chapter 04: what actually goes into the context, and what each part costs."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from render import generate_raw, render_chatml  # noqa: E402

from lantern import case, chat, load_config  # noqa: E402
from lantern.llm import model_info  # noqa: E402
from lantern.ui import (  # noqa: E402
    Table,
    chapter,
    console,
    finding,
    note,
    reply,
    save_shot,
    step,
)

chapter("04", "The briefing", """
Varma has a rule for briefings: the people in the room get the standing orders, a summary of
the case, the documents that matter today, and the minutes of the last meeting. Nothing else.
"A briefing that holds everything holds nothing." She wants LANTERN briefed the same way, and
she wants to see exactly what it was told, word for word.
""")

step("1. The model's chat template: how roles become text")
template = model_info()["template"]
lines = [ln for ln in template.splitlines() if ln.strip()]
ROLE_MARKERS = r"im_start|im_end|\.Content|no_think|\.System }}"
role_lines = [ln for ln in lines if re.search(ROLE_MARKERS, ln)]
excerpt = "\n".join(role_lines[:12])
console.print("[dim]" + excerpt.replace("[", "\\[") + "\n...[/dim]")
note(f"Ollama ships this Go template with the model ({len(lines)} lines). It turns the list of "
     "messages into one string with <|im_start|> and <|im_end|> markers around each role.")

step("2. Assemble the briefing")
ORDERS = ("You are LANTERN, the evidence workstation of the Economic Offences Wing. Answer only "
          "from the documents in <evidence> tags. Cite every fact as [file]. If the documents "
          "do not answer, reply NOT IN EVIDENCE.")
summary = case.read("00-briefing.md")
invoices = "".join(
    f"<file name=\"{p.name}\">\n{p.read_text()}</file>\n"
    for p in case.files("invoices") if p.name.startswith("NW-"))
notes = case.read("reyes-notes.md")
excerpt = notes[notes.index("## Friday 06 February"):].split("\n## ")[0]
history = [
    {"role": "user", "content": "Who found Reyes, and when?"},
    {"role": "assistant", "content": "Ivan Petrov found him at 23:52 [petrov.md]."},
]
question = ("How much has Halcyon paid Northwind Freight in total this year, and what did Reyes "
            "write about Northwind? List each invoice.")

parts = [
    ("system: standing orders", "system", ORDERS),
    ("case summary", "user", f"<case_summary>\n{summary}</case_summary>"),
    ("documents: 3 Northwind invoices", "user", f"<evidence>\n{invoices}"),
    ("documents: Reyes, 6 February", "user",
     f"<file name=\"reyes-notes.md\">\n{excerpt}\n</file>\n</evidence>"),
    ("conversation so far", "history", ""),
    ("the question", "user", question),
]


def build(upto: int) -> list[dict[str, str]]:
    """Messages containing the first `upto` parts of the briefing."""
    system = ORDERS
    first_user = "\n\n".join(p[2] for p in parts[1:4][: max(0, upto - 1)])
    msgs = [{"role": "system", "content": system}]
    if upto >= 5:
        msgs.append({"role": "user", "content": first_user + "\n\nBriefing received?"})
        msgs.append({"role": "assistant", "content": "Briefing received."})
        msgs += history
        msgs.append({"role": "user", "content": question if upto >= 6 else "Ready."})
    else:
        msgs.append({"role": "user", "content": first_user or "Ready."})
    return msgs


costs, previous = [], 0
for i in range(1, len(parts) + 1):
    used = chat(build(i), max_tokens=1).prompt_tokens
    costs.append(used - previous)
    previous = used
num_ctx = load_config()["generation"]["num_ctx"]
reserve = load_config()["generation"]["max_tokens"]
t = Table(title=f"Token budget for one call (num_ctx = {num_ctx:,})")
t.add_column("part")
t.add_column("tokens", justify="right")
t.add_column("share of window", justify="right")
t.add_column("")
for (name, _, _), c in zip(parts, costs, strict=True):
    t.add_row(name, f"{c:,}", f"{c / num_ctx:.1%}", "#" * max(1, round(40 * c / num_ctx)))
t.add_row("reserved for the answer", f"{reserve:,}", f"{reserve / num_ctx:.1%}",
          "." * round(40 * reserve / num_ctx))
free = num_ctx - previous - reserve
t.add_row("[bold]free[/bold]", f"{free:,}", f"{free / num_ctx:.1%}", "")
console.print(t)
note("Counts are measured, not estimated: each row is the increase in prompt tokens reported "
     "by Ollama when that part is added. Template markers are counted with the part they wrap.")

step("3. Exactly what LANTERN reads")
messages = build(len(parts))
rendered = render_chatml(messages)
shown = rendered.replace(invoices, "[... 3 invoice files ...]\n").replace(
    summary, "[... briefing note ...]\n")
console.print(shown.replace("[", "\\[").replace("\\[...", "[dim]\\[...").replace(
    "...]", "...][/dim]"))

step("4. Proof: the chat API sends exactly this text")
via_chat = chat(messages, temperature=0, max_tokens=300)
via_raw = generate_raw(rendered, temperature=0, num_predict=300)
console.print(f"chat endpoint: {via_chat.prompt_tokens:,} prompt tokens | our rendered text sent "
              f"raw: {via_raw['prompt_eval_count']:,} prompt tokens")
reply("answer via the chat endpoint", via_chat.text)
reply("answer via the raw rendered text", via_raw["response"].strip())
note("Same tokens in. Read the two totals. If they differ, the input was identical and the "
     "model still answered differently at temperature 0. Chapter 06 is about exactly that.")

step("5. Do not ask the model to do the arithmetic. Put the result in the context.")
amounts = {p.stem: float(re.search(r"Total due: ([\d,.]+)", p.read_text()).group(1)
                         .replace(",", "")) for p in case.files("invoices")
           if p.name.startswith("NW-")}
total = sum(amounts.values())
computed = ("<computed by=\"D. Okafor, EOW\">\n" + "\n".join(
    f"{k}: {v:,.2f}" for k, v in amounts.items()) + f"\nTOTAL: {total:,.2f}\n</computed>")
console.print(computed.replace("[", "\\["))
fixed = messages[:-1] + [{"role": "user", "content": computed + "\n\n" + question}]
reply("answer with the computed total in the context", chat(fixed, temperature=0,
                                                            max_tokens=300).text)
note("Code adds up money exactly, every time. The model's job is to read and explain.")

finding("""
Three Northwind invoices: NW-0388 for 62,500.00, NW-0402 for 71,200.00 and NW-0419 for
94,000.00. That is 227,700.00 Kestrel Bay dollars in ten weeks to a company Reyes described as
"not a vendor". None of the invoices carries a VAT number. All three are payable to the same
account at Sabran Mercantile Bank.

LANTERN listed the invoices correctly. The total did not hold: the same tokens at temperature 0
produced one figure through the chat endpoint and another through the raw text, and only the
computed total is reliable. It also wrote that Reyes put "Not a vendor" in the margin of an
invoice; the briefing says the margin note was on a ledger page. Varma looks at the token table
longer than at the answer. "So this is everything it knew.
Good. Then everything it said can be checked."
""")
save_shot("04-what-goes-in-context")

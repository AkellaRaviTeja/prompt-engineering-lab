"""Chapter 04: what actually goes into the context, and what each part costs."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from render import generate_raw, render_chatml  # noqa: E402

from lantern import case, chat, learn, load_config  # noqa: E402
from lantern.config import tier  # noqa: E402
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
    your_turn,
)

chapter("04", "The briefing", """
Varma has a rule for briefings: the people in the room get the standing orders, a summary of
the case, the documents that matter today, and the minutes of the last meeting. Nothing else.
"A briefing that holds everything holds nothing." She wants LANTERN briefed the same way, and
she wants to see exactly what it was told, word for word.
""")

step("1. The model's chat template: how roles become text")
HOSTED = tier() == "hosted"
if HOSTED:
    note("Skipped on the hosted tier: the provider does not publish its chat template. The "
         "messages go to its API as a list, and the text the model reads is rendered on its side.")
else:
    template = model_info()["template"]
    lines = [ln for ln in template.splitlines() if ln.strip()]
    ROLE_MARKERS = r"im_start|im_end|\.Content|no_think|\.System }}"
    role_lines = [ln for ln in lines if re.search(ROLE_MARKERS, ln)]
    excerpt = "\n".join(role_lines[:12])
    console.print("[dim]" + excerpt.replace("[", "\\[") + "\n...[/dim]")
    note(f"Ollama ships this Go template with the model ({len(lines)} lines). It turns the list "
         "of messages into one string with <|im_start|> and <|im_end|> markers around each role.")

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
reyes_text = excerpt  # the Reyes document in the briefing
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
     f"<file name=\"reyes-notes.md\">\n{reyes_text}\n</file>\n</evidence>"),
    ("conversation so far", "history", ""),
    ("the question", "user", question),
]
note("The briefing is the `parts` list in run.py. `build()` turns it into messages.")


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


p_part = learn.predict("Which part of the briefing will cost the most tokens?",
                       [name for name, _, _ in parts])
p_total = learn.predict_number("How many prompt tokens will the whole briefing take, template "
                               "markers included?", unit="tokens")
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
learn.reveal(p_part, answer=costs.index(max(costs)),
             why="Documents dominate a briefing. The rules and the question are short; the "
             "material is what fills the window, so it is what you choose most carefully.")
learn.reveal(p_total, actual=previous, tolerance=0.3,
             why=f"{previous:,} tokens is {previous / num_ctx:.0%} of the window. A briefing that "
             "holds only what matters is small; the room left is for the answer and the history.")


def approx_tokens(text: str) -> int:
    """A rough count for budgeting before a call: about four characters per token."""
    return (len(text) + 3) // 4


def assemble(*, rules, summary, documents, history, question, budget, count=approx_tokens):
    """The briefing as messages: rules, case summary, documents, history, question last.

    `documents` is a list of (name, text), most important first. Over `budget` (counted by
    `count` over the message contents), the oldest exchange of history goes first, then the
    least important document. Rules, summary and question are never dropped.
    """
    docs, hist, dropped = list(documents), list(history), []

    def render():
        files = "".join(f'<file name="{n}">\n{t.rstrip()}\n</file>\n' for n, t in docs)
        brief = f"<case_summary>\n{summary.rstrip()}\n</case_summary>"
        if docs:
            brief += f"\n\n<evidence>\n{files}</evidence>"
        return [{"role": "system", "content": rules},
                {"role": "user", "content": brief + "\n\nBriefing received?"},
                {"role": "assistant", "content": "Briefing received."},
                *hist, {"role": "user", "content": question}]

    def size(msgs):
        return sum(count(m["content"]) for m in msgs)

    msgs = render()
    while size(msgs) > budget and hist:
        hist, dropped = hist[2:], [*dropped, "history: " + hist[0]["content"][:40]]
        msgs = render()
    while size(msgs) > budget and docs:
        dropped.append(docs.pop()[0])
        msgs = render()
    if size(msgs) > budget:
        raise ValueError(f"rules, summary and question alone need {size(msgs)} of {budget}")
    return {"messages": msgs, "dropped": dropped, "tokens": size(msgs)}


MINE = learn.mine()
assemble_fn = MINE.assemble if MINE else assemble
docs = [(p.name, p.read_text()) for p in case.files("invoices") if p.name.startswith("NW-")]
docs.append(("reyes-notes.md", reyes_text))

step("3. Exactly what LANTERN reads")
messages = assemble_fn(rules=ORDERS, summary=summary, documents=docs, history=history,
                       question=question, budget=num_ctx - reserve)["messages"]
note("From here on the briefing is built by `assemble()` in run.py: the same parts, in order, "
     "trimmed to a token budget if they do not fit.")
rendered = render_chatml(messages)
if HOSTED:
    note("Skipped on the hosted tier: this is Qwen3's template, and the hosted provider does not "
         "publish the text it renders from the messages.")
else:
    block = "".join(f'<file name="{n}">\n{t.rstrip()}\n</file>\n' for n, t in docs[:3])
    shown = rendered.replace(block, "[... 3 invoice files ...]\n").replace(
        summary.rstrip(), "[... briefing note ...]")
    console.print(shown.replace("[", "\\[").replace("\\[...", "[dim]\\[...").replace(
        "...]", "...][/dim]"))



def stated_total(text: str) -> float:
    """The last amount of 100,000 or more in an answer: its total (0 if it gives none)."""
    amounts = [float(a.replace(",", "")) for a in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
                                                             r"\d{6,}(?:\.\d+)?", text)]
    big = [a for a in amounts if a >= 100_000]
    return big[-1] if big else 0.0


step("4. Proof: the chat API sends exactly this text")
via_chat = chat(messages, temperature=0, max_tokens=300)
if HOSTED:
    note("Skipped on the hosted tier: the raw text comparison sends the rendered string to "
         "Ollama's /api/generate with raw=true. A hosted API takes messages only; it has no "
         "endpoint that reads a pre-rendered prompt, so the answer below is the chat endpoint's.")
    reply("answer via the chat endpoint", via_chat.text)
    raw_tokens, raw_total = 0, 0.0
else:
    p_same = learn.predict(
        "The same tokens go in twice at temperature 0: once through the chat endpoint, once as our "
        "rendered text. What will the two totals be?",
        ["The same, and right (227,700.00)", "The same, and wrong", "Two different totals"],
    )
    via_raw = generate_raw(rendered, temperature=0, num_predict=300)
    console.print(f"chat endpoint: {via_chat.prompt_tokens:,} prompt tokens | our rendered text "
                  f"sent raw: {via_raw['prompt_eval_count']:,} prompt tokens")
    reply("answer via the chat endpoint", via_chat.text)
    reply("answer via the raw rendered text", via_raw["response"].strip())
    note("Same tokens in. Read the two totals. If they differ, the input was identical and the "
         "model still answered differently at temperature 0. Chapter 06 is about exactly that.")
    raw_tokens, raw_total = via_raw["prompt_eval_count"], stated_total(via_raw["response"])
    chat_total = stated_total(via_chat.text)
    learn.reveal(
        p_same,
        answer=2 if chat_total != raw_total else (0 if chat_total == 227_700 else 1),
        why=f"Chat said {chat_total:,.2f}, raw said {raw_total:,.2f}. Identical input is not "
        "identical output: batching and floating point can tip a close choice (chapter 06), and "
        "adding six-digit numbers is not something a small model does reliably.",
    )

step("5. Do not ask the model to do the arithmetic. Put the result in the context.")
amounts = {p.stem: float(re.search(r"Total due: ([\d,.]+)", p.read_text()).group(1)
                         .replace(",", "")) for p in case.files("invoices")
           if p.name.startswith("NW-")}
total = sum(amounts.values())
computed = ("<computed by=\"D. Okafor, EOW\">\n" + "\n".join(
    f"{k}: {v:,.2f}" for k, v in amounts.items()) + f"\nTOTAL: {total:,.2f}\n</computed>")
console.print(computed.replace("[", "\\["))
fixed = messages[:-1] + [{"role": "user", "content": computed + "\n\n" + question}]
p_computed = learn.predict("With Okafor's computed total in the context, will the answer state "
                           "227,700.00?", ["Yes", "No"])
with_computed = chat(fixed, temperature=0, max_tokens=300).text
reply("answer with the computed total in the context", with_computed)
note("Code adds up money exactly, every time. The model's job is to read and explain.")
learn.reveal(p_computed, answer=0 if stated_total(with_computed) == total else 1,
             why="Copying a number from the context is reading, which models do well. Adding six "
             "numbers is arithmetic, which code does exactly.")

step("6. A tighter budget: what gets dropped")
TIGHT_BUDGET = 850  # tokens, as approx_tokens() counts them
tight = assemble_fn(rules=ORDERS, summary=summary, documents=docs, history=history,
                    question=question, budget=TIGHT_BUDGET)
note(f"Budget {TIGHT_BUDGET:,}. Dropped, in order: {', '.join(tight['dropped']) or 'nothing'}.")
tight_reply = chat(tight["messages"], temperature=0, max_tokens=300)
reply("answer from the trimmed briefing", tight_reply.text,
      meta=f"{tight_reply.prompt_tokens:,} prompt tokens")
note("Old conversation goes first, then the least important document. What was dropped cannot "
     "be cited: decide the order of importance before the budget decides it for you.")


def listed(text: str) -> int:
    return sum(n in text for n in ("NW-0388", "NW-0402", "NW-0419"))


learn.record(
    briefing_tokens=previous,
    free_tokens=free,
    chat_prompt_tokens=via_chat.prompt_tokens,
    raw_prompt_tokens=raw_tokens,
    tokens_match=raw_tokens == via_chat.prompt_tokens,
    chat_total=stated_total(via_chat.text),
    raw_total=raw_total,
    chat_total_right=stated_total(via_chat.text) == total,
    computed_total_right=stated_total(with_computed) == total,
    invoices_listed=listed(via_chat.text),
    reyes_line_in_answer="not a vendor" in via_chat.text.lower(),
    tight_dropped=len(tight["dropped"]),
    tight_prompt_tokens=tight_reply.prompt_tokens,
    tight_invoices_listed=listed(tight_reply.text),
    tight_reyes_kept="reyes-notes.md" not in tight["dropped"],
    mine=bool(MINE),
)

your_turn(
    "04",
    check=[
        "In the budget table, which part costs the most tokens? How much of the window is free?",
        "Compare the totals in the two step 4 answers with each other and with "
        "case/invoices/NW-0388.txt, NW-0402.txt and NW-0419.txt.",
        "Each answer says where Reyes wrote about Northwind. Check that against "
        "case/00-briefing.md and the 6 February entry in case/reyes-notes.md.",
    ],
    exercises=[
        "In run.py, remove the <evidence> and <file name=...> tags from `invoices` and from the "
        "`parts` entries. Does the model still cite file names?",
        "In run.py, in `build()`, put `question` at the front of `first_user`, and send 'Answer "
        "it.' in place of `question` in the last user turn. Does the answer change?",
        "In run.py, set `reyes_text = notes` (the full file) in place of `excerpt`. Watch the "
        "budget table and the answer.",
        "In run.py, set `history = []`. Is anything in the answer worse?",
    ],
)

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

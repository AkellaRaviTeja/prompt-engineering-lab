"""Chapter 11: rehearse the Malhotra interview with three personas, and test the 'expert' myth."""

from lantern import case, chat
from lantern.ui import Table, chapter, console, finding, note, reply, save_shot, step

chapter("11", "Rehearsal", """
The interview with Raj Malhotra is booked for Thursday at ten. Marcus Hale will be sitting next to
him. Varma has run a hundred interviews and still rehearses every one. "Hale will attack the
timeline," she says. "Okafor will want the money. And somebody should think like Elena Voss,
because she approved every one of those trips. Let LANTERN play them. Then forget everything it
says that is not in the file."
""")

FINDING = """Our case: R. Malhotra badged out of the administration building at 23:31:02 and out
of Gate 2 at 23:47:09. The walk takes 5 minutes. A route through stairwell C takes 7. The bottom
door of stairwell C was opened from outside at 23:36 with override code OVR-AUD-02. Three
Northwind Freight invoices with no VAT number were each dated while Malhotra was in Port Sabran."""

PERSONAS = {
    "Marcus Hale, defence counsel": """You are Marcus Hale, defence counsel for Halcyon Maritime
and for Raj Malhotra. You are precise, courteous and relentless. Your job is to find every weakness
in the police case and say how you would use it in court. Do not invent facts; attack the
inferences.""",
    "Forensic accountant": """You are a forensic accountant working with a police fraud unit.
You think in money flows, approvals, cost centres and controls. You care about who approved,
who benefited and what documents should exist but do not.""",
    "Elena Voss, CEO (role-play)": """You are playing Elena Voss, CEO of Halcyon Maritime, in an
interview rehearsal. Stay strictly within what her signed statement says. If asked about anything
the statement does not cover, say you would need to check. Never invent facts.

Her statement:
""" + case.read("statements/voss.md"),
}

QUESTIONS = {
    "Marcus Hale, defence counsel": "Here is the police case. List your three strongest "
    "objections, one line each.\n\n" + FINDING,
    "Forensic accountant": "Here is the police case. List the three questions you would put to "
    "Malhotra about the money, one line each.\n\n" + FINDING,
    "Elena Voss, CEO (role-play)": "Ms Voss, why did you approve Raj Malhotra's four trips to "
    "Port Sabran this year?",
}

step("1. Three personas, three system prompts")
for name, persona in PERSONAS.items():
    r = chat(QUESTIONS[name], system=persona, temperature=0.3, max_tokens=350)
    reply(f"LANTERN as {name}", r.text, meta=f"{r.output_tokens} tokens")
note("Same model, same facts. The persona changed focus, vocabulary and what counts as a weakness.")
note("Check the Voss answer against her statement. "
     "Anything not in it is fiction, however plausible.")

step("2. Persona in the system prompt or the user prompt?")
hale = PERSONAS["Marcus Hale, defence counsel"]
q = QUESTIONS["Marcus Hale, defence counsel"]
r_user = chat(f"{hale}\n\n{q}", temperature=0.3, max_tokens=350)
reply("Hale persona inside the user message", r_user.text, meta=f"{r_user.output_tokens} tokens")
note("Both work on one turn. The system prompt version persists across a conversation and is")
note("harder for later turns to override, which is why standing roles belong there (chapter 02).")

step("3. Does 'you are a world-class expert' make it more accurate?")
invoices = "\n\n".join(case.read(f"invoices/{n}.txt") for n in ("NW-0388", "NW-0402", "NW-0419"))
fact_q = ("Which of these three invoices has the largest total, and what is the total? "
          f"Answer as INVOICE-ID AMOUNT.\n\n{invoices}")
EXPERT = "You are a world-class forensic accountant with thirty years of experience."


def correct(text: str) -> bool:
    flat = text.replace(",", "").replace("$", "")
    return "NW-0419" in text and "94000" in flat


seeds = range(1, 5)
table = Table(title=f"Correct answers out of {len(seeds)} runs (temperature 0.7, seeds 1 to 4)")
for col in ("prompt", "max_tokens=40", "max_tokens=400", "avg tokens used (400)"):
    table.add_column(col, justify="left" if col == "prompt" else "right")
for label, system in (("no persona", None), ("expert persona", EXPERT)):
    cells = []
    used = 0
    for budget in (40, 400):
        hits = 0
        for seed in seeds:
            r = chat(fact_q, system=system, temperature=0.7, seed=seed, max_tokens=budget)
            hits += correct(r.text)
            used += r.output_tokens if budget == 400 else 0
        cells.append(f"{hits}/{len(seeds)}")
    table.add_row(label, *cells, str(used // len(seeds)))
console.print(table)
note("At 40 tokens the expert looks far better. It is not smarter: it is terser. Without a")
note("persona the model shows its working first and runs out of budget before the answer.")
note("Give both room and the gap closes. A persona changes style and length, not knowledge.")

finding("""
LANTERN's Hale did not dispute a single timestamp. He attacked the inference: the records show a
badge and a code, not a person. LANTERN's accountant asked who authorised OVR-AUD-02 and what
documents support three invoices with no VAT number. Both questions go on Varma's pad.

The rehearsal Voss said only that she would need to check the records. "Which is exactly what
the real one will say," Varma says. "A role-play is rehearsal, never evidence. Nothing that came
out of it goes in the file."
""")
save_shot("11-personas")

"""Chapter 09: test Malhotra's alibi with a direct answer, free reasoning, set steps, and code."""

import re

from lantern import case, chat
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

chapter("09", "Sixteen minutes", """
Raj Malhotra's statement is two paragraphs long and very calm. He left the administration
building at about 23:30, walked straight to his car, and drove home. Varma puts the badge log and
the gate camera log next to it. "Calm is not the same as true," she says. "Walk me through it,
minute by minute. Then make LANTERN do the same, and show me where it slips."
""")

badge = case.read("badge-log.csv")
rows = "\n".join(line for line in badge.splitlines()
                 if "Malhotra" in line or line.startswith("time"))
walks = "\n".join(case.read("site-facts.md").splitlines()[2:5])
evidence("badge-log.csv (R. Malhotra rows)", rows)
evidence("site-facts.md (walking times)", walks)

# Every prompt gets the same material: Malhotra's badge rows and the walking times.
material = f"""<badge_log rows="R. Malhotra only">
{rows}
</badge_log>
<walking_times>
{walks}
</walking_times>"""
QUESTION = ("Malhotra says he left the administration building at about 23:30 and walked "
            "straight to his car at Gate 2. Do the records support that?")

PROMPTS = {
    "direct": f"{material}\n\n{QUESTION} Answer yes or no, then one sentence.",
    "step by step": f"{material}\n\n{QUESTION} Think step by step, then give your verdict.",
    "set steps": f"""{material}

{QUESTION}
Work through these steps in order. Show each step on its own line.
1. Copy the first row of the badge log (the ADMIN-MAIN row). Write its time.
2. Copy the second row of the badge log (the first GATE-2-PED row). Write its time.
3. Minutes from step 1 to step 2 (round to whole minutes).
4. Walking time, administration building to Gate 2.
5. Unaccounted minutes = step 3 minus step 4.
6. Stairwell C route = (administration building to stairwell C top) + (stairwell C bottom to
   Gate 2). Write the sum.
7. Is the step 6 sum smaller than the step 3 minutes? Answer yes or no.
8. Verdict in one sentence: is "walked straight to his car" supported or not supported?""",
}

note("Each prompt is an entry in the `PROMPTS` dict in run.py. All share `material`.")

results = {}
for name, prompt in PROMPTS.items():
    step(f"{len(results) + 1}. {name}")
    r = chat(prompt, temperature=0, max_tokens=1000)
    results[name] = r
    reply(f"LANTERN, {name}", r.text,
          meta=f"{r.prompt_tokens} in, {r.output_tokens} out, {r.seconds:.0f}s")
    if name == "set steps":
        note("Read it line by line. Every step is a claim you can check against the evidence.")

step("4. The model reads, the program reasons")
note("Keep the steps the model got right (copying times), and give the arithmetic to code.")
times = re.findall(r"\b(\d\d:\d\d:\d\d)\b", results["set steps"].text)
if len(times) >= 2:
    left, gate = times[:2]
else:
    note("LANTERN did not quote two times, so the program reads them from the badge log.")
    left, gate = rows.splitlines()[1][:8], rows.splitlines()[2][:8]


def minutes(t: str) -> float:
    h, m, s = (int(x) for x in t.split(":"))
    return h * 60 + m + s / 60


gap = minutes(gate) - minutes(left)
table = Table(title="Times quoted by LANTERN, arithmetic by Python")
table.add_column("step")
table.add_column("value", justify="right")
table.add_column("source")
table.add_row("Left admin", left, "LANTERN, step 1")
table.add_row("Passed Gate 2", gate, "LANTERN, step 2")
table.add_row("Elapsed", f"{gap:.1f} min", "Python")
table.add_row("Walk admin to Gate 2", "5 min", "site facts")
table.add_row("Unaccounted", f"{gap - 5:.1f} min", "Python")
table.add_row("Stairwell C route", "3 + 4 = 7 min", "site facts")
table.add_row("Stairwell route fits?", "yes" if 7 <= gap else "no", "Python")
console.print(table)

cost = Table(title="What each style cost")
for col in ("style", "output tokens", "seconds"):
    cost.add_column(col, justify="right" if col != "style" else "left")
for name, r in results.items():
    cost.add_row(name, str(r.output_tokens), f"{r.seconds:.0f}")
console.print(cost)
note("Reasoning out loud costs tokens and time. It pays when each step can be checked.")

your_turn(
    "09",
    check=[
        "In the set steps reply, check steps 1 and 2 against the badge-log panel, then step 4 "
        "against the walking times panel. Which step slips?",
        "Where did the direct and step by step replies get their minutes? Compare them with the "
        "table that Python filled in.",
        "In the cost table, how many times more output tokens did step by step use than direct?",
    ],
    exercises=[
        "In run.py, replace the `rows = ...` filter with `rows = badge`, and change "
        "<badge_log rows=\"R. Malhotra only\"> to <badge_log> in `material`. "
        "Which steps fail first?",
        "In run.py, in the \"set steps\" prompt, change step 4 to 'Copy the line from "
        "walking_times that mentions Gate 2 staff car park.' Does quoting fix it?",
        "No edit: run LANTERN_MODEL=qwen3:4b make lesson N=09. Which set steps does the bigger "
        "model get right?",
        "In run.py, in the PROMPTS loop, add think=(name == \"direct\") to the chat(...) call and "
        "raise max_tokens to 4000. Compare direct with step by step in the cost table.",
    ],
)

finding("""
Malhotra badged out of the administration building at 23:31 and out of Gate 2 at 23:47. Sixteen
minutes for a five minute walk. A route down stairwell C takes seven, which leaves nine minutes
inside the stairwell, and Petrov heard the bang at about 23:40.

There is more. The gate camera shows his car leaving at 23:47 and coming back at 23:59, a minute
after Petrov's call. Malhotra told DS Iyer he was home by 00:05. He was never more than twelve
minutes from Pier 9.
""")
save_shot("09-chain-of-thought")

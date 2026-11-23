"""Chapter 01: a vague prompt against a precise one, on the same witness statement."""

import re

from lantern import case, chat, learn
from lantern.ui import chapter, evidence, finding, note, reply, save_shot, step, your_turn

chapter("01", "Day one", """
Inspector Varma does not look up when you come in. She slides a single page across the desk.
"Ivan Petrov. Night supervisor. He found the body." Then she points at the grey workstation
in the corner. "That is LANTERN. It runs here, offline, because evidence never leaves this
building. Ask it what Petrov's statement tells us. Then tell me what it got wrong."
""")

statement = case.read("statements/petrov.md")
evidence("case/statements/petrov.md", statement)
note("This statement is the only material. Both prompts below send it to the same model.")

step("1. The vague prompt")
vague = f"Summarise this.\n\n{statement}"
note("Prompt: 'Summarise this.' plus the statement. No task, no focus, no format.")
note("Watch for: does the reply notice anything odd about the times? Does it add facts?")
p_gap = learn.predict(
    "Will the reply to 'Summarise this.' work out how long Petrov took between the bang and "
    "finding the body?",
    ["Yes, it states the gap in minutes", "No, it summarises without the gap"],
)
r = chat(vague)
reply("LANTERN, vague prompt", r.text, meta=f"{r.prompt_tokens} tokens in, {r.output_tokens} out")
STATED = {"18:00", "21:00", "23:00", "23:30", "23:52", "02:10"}  # every time the statement gives
GAP = r"\b(1[0-3]|ten|eleven|twelve|thirteen)[ -]?min"  # the 12 minutes, however it is written


def times_in(text: str) -> set[str]:
    """Every HH:MM in a reply, without a leading ~."""
    return {f"{int(h):02d}:{m}" for h, m in re.findall(r"\b(\d{1,2}):(\d{2})\b", text)}


vague_gap = bool(re.search(GAP, r.text, re.I))
learn.reveal(
    p_gap,
    answer=0 if vague_gap else 1,
    why="'Summarise' names no target, so the reply is whatever the model thinks matters. The gap "
    "only appears if something in the prompt asks about time taken.",
)

step("2. The precise prompt")
precise = f"""You are reviewing a witness statement for a police inquiry.

Task: build a timeline of what the witness says happened between 23:00 and 23:59.

Rules:
- One line per event, in time order, formatted as `HH:MM | event | quote`.
- The quote must be copied word for word from the statement.
- Convert spoken times to 24-hour time. The night shift runs 18:00 to 06:00, so "twenty to
  twelve" means 23:40.
- If the witness gives an approximate time, write it as `~HH:MM`.
- After the timeline, list any gap where the witness's account does not explain the time taken.
  Use the walking distances the witness gives.

Statement:
<statement>
{statement}
</statement>"""
note("Same statement. Now the prompt says what to do, how to format it, and what to look for.")
note("It is the `precise` variable in run.py: task, rules, format, then the statement in tags.")
p_tokens = learn.predict_number(
    f"The vague prompt cost {r.prompt_tokens} tokens in. How many will the precise prompt cost?",
    unit="tokens",
)
p_2340 = learn.predict(
    "Petrov says the bang came 'at about twenty to twelve'. What time will the timeline give it?",
    ["23:40 or ~23:40", "Some other time", "No time for the bang at all"],
)
p_quotes = learn.predict(
    "The rules say every quote is copied word for word. How many of the timeline's quotes will "
    "really be in the statement?",
    ["Every one", "Most, not all", "Half or fewer", "There will be no timeline lines"],
)
r2 = chat(precise, temperature=0)
reply("LANTERN, precise prompt", r2.text,
      meta=f"{r2.prompt_tokens} tokens in, {r2.output_tokens} out")
learn.reveal(
    p_tokens,
    actual=r2.prompt_tokens,
    tolerance=0.3,
    why=f"Task, rules and tags added {r2.prompt_tokens - r.prompt_tokens} tokens to the same "
    "statement. Structure is cheap next to the evidence it frames.",
)
flat = " ".join(statement.split())
rows = [ln for ln in r2.text.splitlines() if re.match(r"\s*[-*]?\s*~?\d{1,2}:\d{2}\s*\|", ln)]
quotes = [ln.split("|", 2)[2].strip().strip("`\"' ") for ln in rows if ln.count("|") >= 2]
verbatim = sum(1 for q in quotes if q and " ".join(q.split()) in flat)
bang = next((ln for ln in rows if re.search(r"bang", ln, re.I)), "")
bang_at = 0 if re.search(r"~?23:40", bang) else (1 if bang else 2)
learn.reveal(
    p_2340,
    answer=bang_at,
    why="'Twenty to twelve' is 23:40 only because the rules say the shift runs at night. A model "
    "cannot know the shift pattern unless the prompt tells it.",
)
learn.reveal(
    p_quotes,
    answer=3 if not rows else (0 if verbatim == len(rows) else (1 if verbatim > len(rows) / 2
                                                                else 2)),
    why=f"{verbatim} of {len(rows)} timeline quotes match the statement word for word. Asking for "
    "quotes makes the reply checkable; it does not make it true. Check them.",
)

step("3. What changed")
note("The model and the evidence were identical. Only the prompt changed.")
note("The vague prompt gave a summary. The precise prompt gave an artefact you can check.")
note("Check the quotes against the statement yourself. LANTERN is a witness too.")

your_turn(
    "01",
    check=[
        "Petrov hears a bang, then later finds the body. Which reply worked out how long that "
        "took, and whether the walk he describes explains it?",
        "Open case/statements/petrov.md and compare every quote in the precise reply with it. "
        "Is any quote, time or distance not in the statement? That is the model inventing.",
        "Did 'twenty to twelve' become 23:40? Only the rule about the night shift makes it so.",
    ],
    exercises=[
        "In run.py, delete the <statement> and </statement> tags in the `precise` prompt. "
        "Does the timeline format still hold?",
        "In run.py, change 'copied word for word' to 'summarised'. How many details survive?",
        "In run.py, add to the Task line: 'Calculate how long the witness took to reach "
        "stairwell C after the bang.' Does the model find the gap on its own?",
        "No edit: run LANTERN_MODEL=qwen3:4b make lesson N=01 and compare the bigger model.",
    ],
)

learn.record(
    vague_prompt_tokens=r.prompt_tokens,
    precise_prompt_tokens=r2.prompt_tokens,
    vague_found_gap=vague_gap,
    precise_found_gap=bool(re.search(GAP, r2.text, re.I)),
    vague_invented_times=len(times_in(r.text) - STATED - {"23:40"}),
    precise_invented_times=len(times_in(r2.text) - STATED - {"23:40"}),
    timeline_lines=len(rows),
    quotes_verbatim=verbatim,
    bang_at_2340=bang_at == 0,
    shift_rule_in_prompt="night shift" in precise,
)

finding("""
Petrov says he heard a bang at about 23:40. He says the hut is two minutes from stairwell C.
He says he found Reyes at 23:52. That is about twelve minutes to cover a two minute walk, and
he explains it with a cup of tea and a detour past the reefer stacks.

Varma reads the timeline twice. "Good. Now find out why he waited."
""")
save_shot("01-prompt-engineering")

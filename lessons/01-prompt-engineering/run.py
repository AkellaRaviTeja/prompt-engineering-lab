"""Chapter 01: a vague prompt against a precise one, on the same witness statement."""

from lantern import case, chat
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
r = chat(vague)
reply("LANTERN, vague prompt", r.text, meta=f"{r.prompt_tokens} tokens in, {r.output_tokens} out")

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
r2 = chat(precise, temperature=0)
reply("LANTERN, precise prompt", r2.text,
      meta=f"{r2.prompt_tokens} tokens in, {r2.output_tokens} out")

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

finding("""
Petrov says he heard a bang at about 23:40. He says the hut is two minutes from stairwell C.
He says he found Reyes at 23:52. That is about twelve minutes to cover a two minute walk, and
he explains it with a cup of tea and a detour past the reefer stacks.

Varma reads the timeline twice. "Good. Now find out why he waited."
""")
save_shot("01-prompt-engineering")

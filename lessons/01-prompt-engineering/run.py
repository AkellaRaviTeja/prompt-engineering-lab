"""Chapter 01: a vague prompt against a precise one, on the same witness statement."""

from lantern import case, chat
from lantern.ui import chapter, evidence, finding, note, reply, save_shot, step

chapter("01", "Day one", """
Inspector Varma does not look up when you come in. She slides a single page across the desk.
"Ivan Petrov. Night supervisor. He found the body." Then she points at the grey workstation
in the corner. "That is LANTERN. It runs here, offline, because evidence never leaves this
building. Ask it what Petrov's statement tells us. Then tell me what it got wrong."
""")

statement = case.read("statements/petrov.md")
evidence("statements/petrov.md", statement)

step("1. The vague prompt")
vague = f"Summarise this.\n\n{statement}"
note("Prompt: 'Summarise this.' plus the statement. No task, no focus, no format.")
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
r2 = chat(precise, temperature=0)
reply("LANTERN, precise prompt", r2.text,
      meta=f"{r2.prompt_tokens} tokens in, {r2.output_tokens} out")

step("3. What changed")
note("The model and the evidence were identical. Only the prompt changed.")
note("The vague prompt gave a summary. The precise prompt gave an artefact you can check.")
note("Check the quotes against the statement yourself. LANTERN is a witness too.")

finding("""
Petrov says he heard a bang at about 23:40. He says the hut is two minutes from stairwell C.
He says he found Reyes at 23:52. That is about twelve minutes to cover a two minute walk, and
he explains it with a cup of tea and a detour past the reefer stacks.

Varma reads the timeline twice. "Good. Now find out why he waited."
""")
save_shot("01-prompt-engineering")

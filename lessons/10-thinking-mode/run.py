"""Chapter 10: the stairwell C access puzzle, with thinking mode off and on."""

import sys

from lantern import case, chat
from lantern.ui import Table, chapter, console, evidence, finding, note, reply, save_shot, step

chapter("10", "The locked door", """
Stairwell C has two doors. At 23:30 every night the bottom one locks itself. At 23:36 someone
opened it from the quay side. The badge log does not show a name, only a code. Varma has the
facilities manager on the phone and the site rules on her desk. "Before I ask anyone a question
in an interview room," she says, "I want the list of people who could have opened that door. And
the list of people who could not. With reasons."
""")

LARGE = "--large" in sys.argv  # run the thinking step on qwen3:4b (slow on a CPU)

facts = case.read("site-facts.md")
rules = "\n".join(line for line in facts.splitlines() if line.startswith(
    ("- From 23:30", "  without", "  from the", "- Level 3", "- Override", "  OVR-")))
badge = "\n".join(line for line in case.read("badge-log.csv").splitlines()
                  if line.startswith(("time", "23:2", "23:3")))
hut = "\n".join(line for line in case.read("gate-camera-log.csv").splitlines()
                if "HUT" in line or line.startswith("time"))
evidence("site-facts.md (door rules)", rules)
evidence("badge-log.csv (23:28 to 23:37)", badge)

puzzle = f"""<door_rules>
{rules}
</door_rules>
<badge_log>
{badge}
</badge_log>
<hut_camera>
{hut}
</hut_camera>
<other_facts>
- E. Voss was at the Harbour Hotel dinner from 19:30 until after midnight, seen by hundreds.
- T. Reyes badged into STAIR-C-TOP at 23:13 and was inside the stairwell.
- The figure in hi-vis on the hut camera is I. Petrov.
</other_facts>

At 23:36:15 the bottom door of stairwell C was opened from the outside.
Q1. Which credential opened it?
Q2. For each candidate, could they have been the one who opened it from the outside at 23:36:15?
Write COULD or COULD NOT and the record that decides it. Use where each person was and which
credential was used.
  a) T. Reyes
  b) R. Malhotra
  c) E. Voss
  d) I. Petrov
  e) the lift maintenance contractor (holder of OVR-MNT-01)
  f) Brightwater & Co (holder of OVR-AUD-02)
Q3. One sentence: who must be interviewed about this door first?"""

runs = []


def run(label: str, think: bool, max_tokens: int, model: str | None = None) -> None:
    r = chat(puzzle, model=model, think=think, max_tokens=max_tokens,
             temperature=0.6 if think else 0)
    runs.append((label, r))
    if r.thinking:
        excerpt = r.thinking[:1400] + ("\n\n[...]" if len(r.thinking) > 1400 else "")
        reply(f"{label}: thinking (first 1400 chars of {len(r.thinking)})", excerpt,
              style="magenta")
    reply(f"{label}: answer", r.text or "(empty: the budget ran out while it was still thinking)",
          meta=f"{r.output_tokens} tokens out, {r.seconds:.0f}s",
          style="green" if r.text else "red")


step("1. Thinking off")
note("think=False: the model starts writing the answer at once.")
run("think off", think=False, max_tokens=700)

step("2. Thinking on, small budget")
note("think=True with max_tokens=300. Thinking tokens come out of the same budget as the answer.")
run("think on, 300 tokens", think=True, max_tokens=300)

step("3. Thinking on, room to finish")
note("think=True with max_tokens=4000. Qwen recommends temperature 0.6 for thinking mode.")
if LARGE:
    note("--large: this step runs on qwen3:4b. Expect several minutes on a CPU.")
run("think on, 4000 tokens" + (" (4b)" if LARGE else ""), think=True, max_tokens=4000,
    model="large" if LARGE else None)

step("4. What thinking cost")
table = Table(title="Same puzzle, three runs")
for col in ("run", "thinking chars", "answer chars", "tokens out", "seconds"):
    table.add_column(col, justify="left" if col == "run" else "right")
for label, r in runs:
    table.add_row(label, str(len(r.thinking)), str(len(r.text)), str(r.output_tokens),
                  f"{r.seconds:.0f}")
console.print(table)
note("Check every COULD and COULD NOT against the records. "
     "Thinking makes a model slower, not honest.")

finding("""
The door was not opened with a badge. It was opened with OVR-AUD-02, a contractor override code
that facilities issued to Brightwater & Co on 10 February for the audit and never revoked. The
lift contractor's code stopped working at 18:00. Petrov is on the hut camera from 23:29 to 23:44.
Voss was at a dinner with several hundred witnesses. Reyes was already inside the stairwell.

Brightwater's audit was led by Simon Clarke. He is the man who signed off Halcyon's accounts, and
the man who texted Reyes at 21:44 to ask if he was still at the office.
""")
save_shot("10-thinking-mode")

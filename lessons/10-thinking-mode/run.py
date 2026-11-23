"""Chapter 10: the stairwell C access puzzle, with thinking mode off and on."""

import csv
import io
import re
import sys

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


note("The prompt is the `puzzle` variable in run.py. Every run below sends it.")

step("1. Thinking off")
note("think=False: the model starts writing the answer at once.")
run("think off", think=False, max_tokens=700)

step("2. Thinking on, small budget")
note("think=True with max_tokens=300. Thinking tokens come out of the same budget as the answer.")
p_small = learn.predict(
    "Thinking on, and 300 tokens in all for thinking and answer. What will come back?",
    ["a complete answer", "an answer cut off part way",
     "no answer at all: the budget runs out while it is still thinking"])
run("think on, 300 tokens", think=True, max_tokens=300)
small = runs[-1][1]
learn.reveal(
    p_small,
    answer=2 if not small.text else (1 if small.stop_reason in ("length", "max_tokens") else 0),
    why=f"It wrote {len(small.thinking):,} characters of thinking and {len(small.text):,} of "
    "answer. Thinking tokens are output tokens: they are spent first, from the same max_tokens.",
)

step("3. Thinking on, room to finish")
note("think=True with max_tokens=4000. Qwen recommends temperature 0.6 for thinking mode.")
if LARGE:
    note("--large: this step runs on qwen3:4b. Expect several minutes on a CPU.")
p_long = learn.predict_number(
    "With 4,000 tokens of room, how many output tokens (thinking and answer together) will it "
    "use?", unit="tokens")
run("think on, 4000 tokens" + (" (4b)" if LARGE else ""), think=True, max_tokens=4000,
    model="large" if LARGE else None)
learn.reveal(p_long, actual=runs[-1][1].output_tokens, tolerance=0.3,
             why="A thinking model decides for itself how long to think, and on a puzzle with six "
             "candidates it thinks at length. Budget for the long tail, not the average.")

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

# Step 5: the same question answered by code, from the same records, to score every run.
OVERRIDES = {
    "OVR-MNT-01": {"holder": "the lift maintenance contractor", "valid": ("08:00", "18:00")},
    "OVR-AUD-02": {"holder": "Brightwater & Co", "valid": None},  # never revoked
}
ALIBIS = {
    "T. Reyes": "inside the stairwell from 23:13 (STAIR-C-TOP); the door was opened from outside",
    "R. Malhotra": None,  # badged out of admin at 23:31, nothing places him at 23:36
    "E. Voss": "at the Harbour Hotel dinner from 19:30, seen by hundreds",
    "I. Petrov": "on the hut camera from 23:29:50 to 23:44:12",
}


def hhmm(t: str) -> int:
    h, m = (int(x) for x in t.split(":")[:2])
    return h * 60 + m


def door_candidates(log_csv: str, *, door: str, at: str, overrides: dict,
                    alibis: dict) -> dict:
    """Who could have opened `door` from outside at `at`. The exercise in practice/ builds this."""
    row = next((r for r in csv.DictReader(io.StringIO(log_csv))
                if r["door"] == door and r["time"] == at and r["direction"] == "in"), None)
    if row is None:
        raise ValueError(f"no entry through {door} at {at} in the log")
    cred = row["badge_id"]
    could, ruled_out = [], {}
    for code, o in overrides.items():
        start, end = o["valid"] or ("00:00", "23:59")
        valid = hhmm(start) <= hhmm(at) <= hhmm(end)
        hours = "" if o["valid"] is None else f"valid {start} to {end} only"
        if code == cred and valid:
            could.append(o["holder"])
        elif code == cred:
            ruled_out[o["holder"]] = f"{code} is {hours}"
        else:
            ruled_out[o["holder"]] = f"{code} was not used" + (f", and is {hours}" if hours else "")
    if cred not in overrides:
        could.append(row["holder"])
    for person, alibi in alibis.items():
        if person not in could and alibi:
            ruled_out[person] = alibi
    not_ruled_out = [p for p, a in alibis.items() if not a and p not in could]
    return {"credential": cred, "could": could, "ruled_out": ruled_out,
            "not_ruled_out": not_ruled_out}


LETTER = {"a": "T. Reyes", "b": "R. Malhotra", "c": "E. Voss", "d": "I. Petrov",
          "e": "the lift maintenance contractor", "f": "Brightwater & Co"}


def verdicts(text: str) -> dict[str, str]:
    """COULD or COULD NOT for each lettered candidate a) to f) in a model's answer."""
    parts = re.split(r"(?im)^[\W_]*([a-f])\)", text)
    out = {}
    for letter, body in zip(parts[1::2], parts[2::2], strict=False):
        # The first verdict word decides: a closing summary ("All candidates COULD NOT except
        # f)") lands in the last candidate's body and must not overrule its own verdict.
        m = re.search(r"COULD\s+NOT|COULDN'T|CANNOT|COULD", body.upper())
        if m:
            out[letter.lower()] = "COULD" if m.group(0) == "COULD" else "COULD NOT"
    return out


step("5. The same question, answered by code")
p_best = learn.predict(
    "Code now answers Q2 from the records: who could, who could not. Of the six candidates, how "
    "many will the best of the three LANTERN answers get right?",
    ["0 to 2", "3 or 4", "5", "all 6"])
truth = door_candidates(case.read("badge-log.csv"), door="STAIR-C-BOTTOM", at="23:36:15",
                        overrides=OVERRIDES, alibis=ALIBIS)
expected = {k: "COULD" if v in truth["could"] or v in truth["not_ruled_out"] else "COULD NOT"
            for k, v in LETTER.items()}
check = Table(title=f"Opened with {truth['credential']}: who could have been at the door")
for col in ("candidate", "by the records", "reason", *[label for label, _ in runs]):
    check.add_column(col)
scores = []
for _, r in runs:
    got = verdicts(r.text)
    scores.append(sum(got.get(k) == v for k, v in expected.items()))
for k, person in LETTER.items():
    reason = truth["ruled_out"].get(person) or (
        "holds the code that opened it" if person in truth["could"]
        else "nothing places them elsewhere; could have had the code")
    check.add_row(f"{k}) {person}", expected[k], reason,
                  *[verdicts(r.text).get(k, "-") for _, r in runs])
check.add_row("right of 6", "", "", *[str(n) for n in scores])
console.print(check)
learn.reveal(p_best, answer=learn.bucket(max(scores), [2, 4, 5]),
             why="The records decide five of the six candidates outright and leave one open. A "
             "dozen lines of code get every one right in milliseconds; use the check to score the "
             "model, not the model to replace the check.")
credential_right = [truth["credential"] in r.text for _, r in runs]
learn.record(
    think_off_right=scores[0],
    small_budget_right=scores[1],
    long_budget_right=scores[2],
    best_right=max(scores),
    credential_named=sum(credential_right),
    think_off_tokens=runs[0][1].output_tokens,
    small_budget_tokens=runs[1][1].output_tokens,
    small_budget_answer_chars=len(runs[1][1].text),
    long_budget_tokens=runs[2][1].output_tokens,
    long_budget_answer_chars=len(runs[2][1].text),
    long_budget_thinking_chars=len(runs[2][1].thinking),
    think_off_seconds=round(runs[0][1].seconds, 1),
    long_budget_seconds=round(runs[2][1].seconds, 1),
    large=LARGE,
)

your_turn(
    "10",
    check=[
        "Which credential did each answer name for Q1? Find the 23:36:15 row in "
        "case/badge-log.csv and check.",
        "Open case/site-facts.md and read the hours each override code is valid. Did each answer "
        "use them when it wrote COULD or COULD NOT?",
        "In the 'Same puzzle, three runs' table, which run spent its whole budget thinking "
        "and left no answer?",
    ],
    exercises=[
        "In run.py, change max_tokens=4000 in step 3's run(...) call to 8000, then run make "
        "lesson N=10 ARGS=--large. How long does it take, and is the answer right?",
        "In run.py, change max_tokens=300 in step 2's run(...) call to 1200. Does an answer "
        "appear, and is it any better than thinking off?",
        "In run.py, inside run(), change chat(puzzle, ...) to chat(puzzle if think else puzzle + "
        "\" Think step by step.\", ...). Compare step 1's tokens and accuracy with step 3.",
        "In run.py, in `puzzle`, change Q2 to ask whether each candidate CAN or CANNOT open it, "
        "and put candidates e) and f) on one line. What changes?",
        "In run.py, delete the <other_facts> block from `puzzle`, tags and all. Which candidates "
        "can no longer be ruled out, by you or the model?",
    ],
)

finding("""
The door was not opened with a badge. It was opened with OVR-AUD-02, a contractor override code
that facilities issued to Brightwater & Co on 10 February for the audit and never revoked. The
lift contractor's code stopped working at 18:00. Petrov is on the hut camera from 23:29 to 23:44.
Voss was at a dinner with several hundred witnesses. Reyes was already inside the stairwell.

Brightwater's audit was led by Simon Clarke. He is the man who signed off Halcyon's accounts, and
the man who texted Reyes at 21:44 to ask if he was still at the office.
""")
save_shot("10-thinking-mode")

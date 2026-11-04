"""Chapter 07: sort phone messages with zero-shot, one-shot and few-shot prompts, and measure."""

import time
from collections import Counter

from lantern import case, chat
from lantern.ui import Table, chapter, console, evidence, finding, note, reply, save_shot, step

LABELS = ["threat", "logistics", "personal"]

chapter("07", "Forty-eight messages", """
Digital forensics has pulled the messages from Reyes's work phone, 1 to 14 March. Forty-eight of
them. Okafor has already sorted them by hand into three piles: threat, logistics, personal. Varma
does not want his piles. She wants to know whether LANTERN can sort the next phone on its own,
because there will be a next phone. "Show me how often it agrees with Daniel," she says. "And show
me where it doesn't."
""")

messages = case.jsonl("messages.jsonl")
by_id = {m["id"]: m for m in messages}
evidence("messages.jsonl (first 4 of 48)", "\n".join(
    f"{m['id']}  {m['time']}  {m['from']:<20} {m['text']}" for m in messages[:4]))

# Two example sets. Every message used as an example in any mode is held out of scoring.
EASY = ["M03", "M02", "M01", "M12", "M04", "M05"]  # clear cases, two per label, interleaved
BORDER = ["M16", "M24", "M33", "M26", "M15", "M10"]  # judgement calls on the label boundaries
scored = [m for m in messages if m["id"] not in EASY + BORDER]

TASK = """Classify a text message from a company executive's work phone.
Labels:
- threat: intimidation, pressure or warnings aimed at the recipient
- logistics: work operations, schedules, deliveries, invoices
- personal: family, friends, health, private life
Answer with exactly one word: threat, logistics or personal."""
PRIMED = TASK.replace("a company executive's", "a murdered company executive's")


def ask(m: dict) -> str:
    return f"Message from {m['from']}: \"{m['text']}\""


def examples_as_turns(ids: list[str]) -> list[dict]:
    """Few-shot examples as earlier chat turns: the shape chat models were trained on."""
    turns = []
    for i in ids:
        turns += [{"role": "user", "content": ask(by_id[i])},
                  {"role": "assistant", "content": by_id[i]["label"]}]
    return turns


def parse(text: str) -> str:
    for word in text.lower().replace(".", " ").replace(":", " ").split():
        if word in LABELS:
            return word
    return "invalid"


MODES = {
    "zero-shot, primed": (PRIMED, []),
    "zero-shot": (TASK, []),
    "one-shot": (TASK, ["M16"]),
    "few-shot, clear examples": (TASK, EASY),
    "few-shot, boundary only": (TASK, BORDER),
}

step("1. What the model actually receives in few-shot")
convo = examples_as_turns(EASY[:2]) + [{"role": "user", "content": ask(by_id["M07"])}]
reply("few-shot as chat turns (first 2 of 6 examples)", "```text\n" + "\n".join(
    f"{t['role']:>9}: {t['content']}" for t in [{"role": "system", "content": "(the task)"},
                                                 *convo]) + "\n```", style="blue")
note("Each example is a user turn and the 'right' assistant reply. "
     "The model continues the pattern.")

step(f"2. Five prompts, {len(scored)} held-out messages each")
results: dict[str, dict] = {}
for mode, (system, ids) in MODES.items():
    start = time.perf_counter()
    preds, tokens = [], 0
    for m in scored:
        r = chat([*examples_as_turns(ids), {"role": "user", "content": ask(m)}], system=system,
                 temperature=0, max_tokens=8)
        preds.append(parse(r.text))
        tokens += r.prompt_tokens
    correct = sum(p == m["label"] for p, m in zip(preds, scored, strict=True))
    results[mode] = {"preds": preds, "acc": correct / len(scored), "tokens": tokens,
                     "secs": time.perf_counter() - start, "counts": Counter(preds)}

table = Table(title="Agreement with Okafor's labels (qwen3:1.7b, temperature 0)")
for col in ("prompt", "examples", "accuracy", "threat", "logistics", "personal", "invalid",
            "tokens/msg"):
    table.add_column(col, justify="left" if col == "prompt" else "right")
for mode, res in results.items():
    c = res["counts"]
    table.add_row(mode, str(len(MODES[mode][1])), f"{res['acc']:.0%}", str(c["threat"]),
                  str(c["logistics"]), str(c["personal"]), str(c["invalid"]),
                  str(res["tokens"] // len(scored)))
gold = Counter(m["label"] for m in scored)
table.add_row("[dim]Okafor (gold)[/dim]", "", "", str(gold["threat"]), str(gold["logistics"]),
              str(gold["personal"]), "", "")
console.print(table)
note("One word in the task, 'murdered', changes how many messages look like threats.")
note("Examples cost tokens on every call. They earn their place only if accuracy moves.")

best = max(results, key=lambda k: results[k]["acc"])
step(f"3. Where the best prompt ({best}) disagrees with Okafor")
preds = results[best]["preds"]
confusion = Counter((m["label"], p) for m, p in zip(scored, preds, strict=True))
ct = Table(title="Confusion table (rows: Okafor, columns: LANTERN)")
ct.add_column("gold \\ predicted")
for lab in [*LABELS, "invalid"]:
    ct.add_column(lab, justify="right")
for g in LABELS:
    ct.add_row(g, *[str(confusion[(g, p)]) for p in [*LABELS, "invalid"]])
console.print(ct)
wrong = Table(title="Disagreements")
for col in ("id", "from", "message", "Okafor", "LANTERN"):
    wrong.add_column(col)
for m, p in zip(scored, preds, strict=True):
    if p != m["label"]:
        wrong.add_row(m["id"], m["from"], m["text"], m["label"], p)
console.print(wrong)
note("Read each disagreement before blaming the model. "
     "Some of Okafor's labels are judgement calls.")
note("M47, Simon Clarke at 21:44 on the night: 'Are you still at the office?' Okafor says threat.")
note("On its own the text is harmless. "
     "It is a threat only if you know what happened two hours later.")

finding(f"""
Best prompt on this phone: {best}, {results[best]['acc']:.0%} agreement with Okafor. The threats
come from one number, +88 301, the same prefix as Northwind's bank in Port Sabran. They start on
1 March and end at 15:03 on 14 March with a place and a time: "Stairwell C. 23:30."

Four more messages Okafor filed as threats are not from that number. Two are from Raj Malhotra.
Two are from Simon Clarke.
""")
save_shot("07-zero-one-few-shot")

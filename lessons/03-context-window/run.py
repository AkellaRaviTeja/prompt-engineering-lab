"""Chapter 03: the context window. What happens when the evidence does not fit."""

import re
import time

from lantern import case, chat, learn, load_config
from lantern.config import tier
from lantern.llm import context_length
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

chapter("03", "Forty pages", """
Digital forensics delivers Reyes's personal notes: thirty-seven entries, January to the night
he died, most of them about fuel prices and payroll. Varma drops the printout on your desk.
"Somewhere in there he says what he found. Feed the lot to LANTERN and ask." You paste the
whole file into one prompt and ask. LANTERN answers at once, and with confidence: Reyes never
mentions Northwind. You have read the anonymous envelope. You know that cannot be true.
""")

notes = case.read("reyes-notes.md")
entries = notes.count("\n## ")
pos = notes.index("Northwind is not a vendor")
evidence("reyes-notes.md", f"{entries} dated entries, {len(notes.split()):,} words. "
         f"The sentence 'Northwind is not a vendor' starts at character {pos:,} of "
         f"{len(notes):,}: {pos / len(notes):.0%} of the way through.")
QUESTION = ("\n\nQuestion: What does Reyes say about Northwind Freight? Quote his exact words. "
            "If the notes do not mention Northwind, say NOT FOUND.")
note("The question is the `QUESTION` variable in run.py. Every step sends it after the notes.")

step("1. Two different limits")
cfg = load_config()["generation"]
trained = context_length()
t = Table()
t.add_column("limit")
t.add_column("tokens", justify="right")
t.add_column("set by")
t.add_row("trained context length", f"{trained:,}", "the model's training (read from its metadata)")
t.add_row("num_ctx (this lab's default)", f"{cfg['num_ctx']:,}",
          "config.yaml, sent with every call")
t.add_row("Ollama's own default", "4,096 or less", "used when you send no num_ctx at all")
console.print(t)
note("The window holds the prompt AND the answer being written. Memory grows with num_ctx, "
     "which is why servers keep it smaller than the model could handle.")



def found(text: str) -> bool:
    """Did a reply give Reyes's line? (It must say 'not a vendor', not just name Northwind.)"""
    return "not a vendor" in text.lower()


step("2. The whole file in a 2,048 token window")
if tier() == "hosted":
    note("num_ctx is an Ollama setting. The hosted provider has one fixed window (1,000,000 "
         "tokens for this model) and rejects a prompt that does not fit rather than cutting it, "
         "so on this tier steps 2 and 3 send the same thing and nothing is dropped.")
p_seen = learn.predict_number(
    "The notes and the question are about 6,400 tokens. The window is 2,048. How many prompt "
    "tokens will the model actually see?",
    unit="tokens",
)
small = chat(notes + QUESTION, num_ctx=2048, temperature=0, max_tokens=200)
reply("num_ctx = 2048", small.text, meta=f"prompt tokens the model actually saw: "
      f"{small.prompt_tokens:,}", style="red")
note(f"Ollama kept {small.prompt_tokens:,} tokens and threw the rest away. No error, no "
     "warning in the reply. It drops from the FRONT, so the question at the end survived "
     "and the evidence did not.")
learn.reveal(
    p_seen,
    actual=small.prompt_tokens,
    tolerance=0.3,
    why="The window holds the prompt and the answer together, and Ollama keeps the most recent "
    "tokens, so the prompt is cut to about half the window. No error is raised.",
)

step("3. The whole file in an 8,192 token window")
p_big = learn.predict(
    "Now every token fits. Will LANTERN find Reyes's line about Northwind?",
    ["Yes, it gives the line", "No, it misses it"],
)
t0 = time.perf_counter()
big = chat(notes + QUESTION, num_ctx=8192, temperature=0, max_tokens=200)
big_seconds = time.perf_counter() - t0
reply("num_ctx = 8192", big.text, meta=f"prompt tokens: {big.prompt_tokens:,}", style="yellow")
note("Every token fits now. Check what the model did with them. A line in the middle of a long "
     "prompt gets the least attention: 'lost in the middle'. Fitting is not the same as reading.")
learn.reveal(
    p_big,
    answer=0 if found(big.text) else 1,
    why="Fitting is not reading. The line sits in the middle of a long prompt, where a small model "
    "attends least, and the result changes with the wording of the question.",
)

step("4. An application that 'fits' the file by keeping the start and the end")
quarter = len(notes) // 4
head_tail = notes[:quarter] + "\n\n[... middle of the document removed to fit ...]\n\n" + \
    notes[-quarter:]
cut = chat(head_tail + QUESTION, num_ctx=8192, temperature=0, max_tokens=200)
reply("first quarter + last quarter", cut.text, meta=f"prompt tokens: {cut.prompt_tokens:,}",
      style="yellow")
note("Keeping the start and end is a common way to squeeze a long document. It is exactly the "
     "wrong cut when the evidence is in the middle.")

step("5. Read it in pieces: one question per chunk")
CHUNKS = 4  # how many pieces to cut the notes into
OVERLAP = 1  # entries each chunk repeats from the one before (used by --mine)


def chunk_notes(text: str, chunks: int) -> list[str]:
    """The notes cut on entry boundaries into `chunks` pieces of whole entries."""
    parts = text.split("\n## ")
    size = len(parts) // chunks + 1
    return ["\n## ".join(parts[i * size:(i + 1) * size]) for i in range(chunks)]


def read_notes(text: str, question: str, *, chat=chat) -> dict:
    """The map step: the question asked of every chunk, one call each."""
    replies = []
    for chunk in chunk_notes(text, CHUNKS):
        r = chat(f"<notes>\n{chunk}\n</notes>{question}", num_ctx=8192, temperature=0,
                 max_tokens=150)
        replies.append({"chunk": chunk, "text": r.text, "prompt_tokens": r.prompt_tokens,
                        "found": "NOT FOUND" not in r.text})
    return {"replies": replies}


MINE = learn.mine()
p_chunks = learn.predict(
    f"The notes go in {CHUNKS} pieces, the same question to each. How many pieces will come back "
    "with Reyes's line?",
    ["None", "Exactly one", "More than one"],
)
t0 = time.perf_counter()
if MINE:
    size = len(notes.split("\n## ")) // CHUNKS + 1
    out = MINE.read_notes(notes, QUESTION, chat=chat, size=size, overlap=OVERLAP)
else:
    out = read_notes(notes, QUESTION)
chunk_seconds = time.perf_counter() - t0
n = len(out["replies"])
for i, r in enumerate(out["replies"]):
    reply(f"chunk {i + 1} of {n}",
          r["text"], meta=f"{r['prompt_tokens']:,} tokens", style="green" if r["found"] else "dim")
note(f"{CHUNKS} short prompts, each small enough to be read properly. This is the idea behind "
     "map-reduce summarising and, in a later case file, retrieval.")
hits = [r for r in out["replies"] if found(r["text"])]
flat_notes = " ".join(notes.split())
quoted = [q for r in hits for q in re.findall(r'["\u201c]([^"\u201d]{12,})["\u201d]', r["text"])]
verbatim = any("not a vendor" in q.lower() and " ".join(q.split()) in flat_notes for q in quoted)
learn.reveal(
    p_chunks,
    answer=min(len(hits), 2),
    why="Each chunk is short enough to be read properly, and the line sits in exactly one of them. "
    "A piece without it should say NOT FOUND; one that claims a hit without the line is a false "
    "alarm, which is why the reduce step checks the quote.",
)
learn.record(
    trained_context=trained,
    small_prompt_tokens=small.prompt_tokens,
    small_found=found(small.text),
    big_prompt_tokens=big.prompt_tokens,
    big_found=found(big.text),
    big_seconds=round(big_seconds, 1),
    headtail_prompt_tokens=cut.prompt_tokens,
    headtail_found=found(cut.text),
    chunks=n,
    chunk_hits=len(hits),
    chunk_found=bool(hits),
    chunk_quote_verbatim=verbatim,
    chunk_seconds=round(chunk_seconds, 1),
    mine=bool(MINE),
)

your_turn(
    "03",
    check=[
        "Compare the prompt tokens under each reply with the size of the notes. In which windows "
        "did the model see the whole file?",
        "Step 3 held every token. Did its answer find the line? Open case/reyes-notes.md, search "
        "for 'Northwind is not a vendor' and check any quote word for word.",
        "In step 4, which part of the notes was cut? Compare with where the evidence panel at "
        "the top says the Northwind sentence sits.",
    ],
    exercises=[
        "In run.py, change `QUESTION` to ask 'What does Reyes say about Northwind?' (drop "
        "'Freight'). Read step 3. Run it twice more. How stable is it?",
        "In run.py, in the `small = chat(...)` line, send QUESTION + notes in place of "
        "notes + QUESTION. What does the model answer when the question is what gets dropped?",
        "In run.py, in the `big = chat(...)` line, change num_ctx=8192 to num_ctx=6400 "
        "(max_tokens is already 200). How long is the answer?",
        "In run.py, step 5, change CHUNKS = 4 to CHUNKS = 8. Is it faster or slower overall? "
        "Does it still find the line?",
    ],
)

finding("""
In a 2,048 token window LANTERN saw a sixth of the notes and said Northwind was never
mentioned. In an 8,192 token window the whole file fitted, and it still missed the line in the
middle. Cutting the middle out made sure of it. Read in four pieces, the entry from 6 February
surfaced: "Northwind is not a vendor. It has no ships, no staff and no office, only a PO box in
Port Sabran." Every payment, Reyes wrote, was coded to Raj Malhotra's cost centre and dated
while Malhotra was in Port Sabran.

Varma reads it twice. "He knew five weeks before he died. Who else did?"
""")
save_shot("03-context-window")

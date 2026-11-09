"""Chapter 03: the context window. What happens when the evidence does not fit."""

from lantern import case, chat, load_config
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

step("2. The whole file in a 2,048 token window")
small = chat(notes + QUESTION, num_ctx=2048, temperature=0, max_tokens=200)
reply("num_ctx = 2048", small.text, meta=f"prompt tokens the model actually saw: "
      f"{small.prompt_tokens:,}", style="red")
note(f"Ollama kept {small.prompt_tokens:,} tokens and threw the rest away. No error, no "
     "warning in the reply. It drops from the FRONT, so the question at the end survived "
     "and the evidence did not.")

step("3. The whole file in an 8,192 token window")
big = chat(notes + QUESTION, num_ctx=8192, temperature=0, max_tokens=200)
reply("num_ctx = 8192", big.text, meta=f"prompt tokens: {big.prompt_tokens:,}", style="yellow")
note("Every token fits now. Check what the model did with them. A line in the middle of a long "
     "prompt gets the least attention: 'lost in the middle'. Fitting is not the same as reading.")

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
parts = notes.split("\n## ")
size = len(parts) // CHUNKS + 1
for i in range(CHUNKS):
    chunk = "\n## ".join(parts[i * size:(i + 1) * size])
    r = chat(f"<notes>\n{chunk}\n</notes>{QUESTION}", num_ctx=8192, temperature=0,
             max_tokens=150)
    found = "NOT FOUND" not in r.text
    reply(f"chunk {i + 1} of {CHUNKS}",
          r.text, meta=f"{r.prompt_tokens:,} tokens", style="green" if found else "dim")
note(f"{CHUNKS} short prompts, each small enough to be read properly. This is the idea behind "
     "map-reduce summarising and, in a later case file, retrieval.")

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

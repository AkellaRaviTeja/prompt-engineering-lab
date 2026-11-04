"""Chapter 06: temperature 0, why answers still change, and how to make a finding reproducible."""

import hashlib
import json
import math
import random
import sys
from datetime import UTC, datetime
from functools import reduce
from operator import add
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons" / "05-temperature-and-top-k"))

from sampling import first_token_distribution, northwind_messages  # noqa: E402

from lantern import case, chat, load_config  # noqa: E402
from lantern.config import model_name  # noqa: E402
from lantern.ui import (  # noqa: E402
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    reply,
    save_shot,
    step,
)

chapter("06", "The letter", """
The letter from Hale Brennan LLP arrives by courier at nine. Varma reads it standing up, then
hands it to you. "He is not wrong," she says, which is the most worrying thing she has said
all week. "If LANTERN gives two answers to one question, he will put both in front of a jury
and ask them to pick. Find out whether he can. Then make sure he can't."
""")
letter = case.read("hale-letter.md")
evidence("hale-letter.md", letter[letter.index("First,"):letter.index("Third,")].strip())

QUESTION = ("Northwind invoices: NW-0388 62,500.00; NW-0402 71,200.00; NW-0419 94,000.00. "
            "What is the total? Reply with one number only, no working.")

step("1. Temperature 0: always take the most likely token")
note("Greedy decoding. No randomness is drawn, so the seed does not matter. Five runs:")
answers = [chat(QUESTION, temperature=0, max_tokens=60).text for _ in range(5)]
for i, a in enumerate(answers, 1):
    console.print(f"  run {i}: {a}")
console.print(f"[bold]{len(set(answers))} distinct answer(s) in 5 runs.[/bold] "
              f"The correct total is {62500 + 71200 + 94000:,.2f}.")
note("Deterministic is not the same as correct. A model can be reliably wrong.")

step("2. Same input, different numbers: what the server did before matters")
host = load_config()["ollama"]["host"]


def top_prob(**kw) -> tuple[str, float]:
    r = chat(northwind_messages(), temperature=1.0, top_k=40, top_p=1.0, logprobs=3,
             max_tokens=1, **kw)
    tok, lp = first_token_distribution(r)[0]
    return tok, math.exp(lp)


t = Table(title="Probability of the top next token after 'Northwind is most likely a'")
t.add_column("server state")
t.add_column("token")
t.add_column("probability", justify="right")
for label, kw in (("model just reloaded (num_ctx 4096)", {"num_ctx": 4096}),
                  ("model just reloaded (num_ctx 8192)", {}),
                  ("same request again, prompt cached", {}),
                  ("and again", {})):
    tok, p = top_prob(**kw)
    t.add_row(label, repr(tok), f"{p:.4f}")
console.print(t)
note("Identical tokens in. When the server computes the whole prompt fresh it does the "
     "arithmetic in one shape; when it reuses a cached prefix, in another. Floating point "
     "gives slightly different results for each, so the probabilities move.")

step("3. Why the shape of the arithmetic matters: floating point is not associative")
a, b, c = 0.1, 0.2, 0.3
console.print(f"(0.1 + 0.2) + 0.3 = {(a + b) + c!r}")
console.print(f"0.1 + (0.2 + 0.3) = {a + (b + c)!r}")
big, small = 1e16, 1.0
console.print(f"(1e16 + 1.0) - 1e16 = {(big + small) - big!r}")
console.print(f"(1e16 - 1e16) + 1.0 = {(big - big) + small!r}")
rng = random.Random(14)
values = [rng.random() for _ in range(10_000)]
# Plain left-to-right addition, as a GPU kernel does it. (Python's built-in sum() uses a
# compensated algorithm that hides the effect, so it is not used here.)
totals = sorted({reduce(add, rng.sample(values, len(values))) for _ in range(5)})
console.print(f"10,000 numbers added in 5 random orders gave {len(totals)} different totals:")
for total in totals:
    console.print(f"  {total!r}")
note("A GPU adds up thousands of products in parallel, in an order that depends on batch size "
     "and kernel choice. A different order gives a different last digit.")

step("4. When a last digit becomes a different answer")
logits = {" 227": 15.2041733, " 226": 15.2041729}
console.print("Two candidate tokens with almost equal scores:")
for tok, v in logits.items():
    console.print(f"  {tok!r}: {v}")
for noise in (0.0, -0.000001):
    shifted = {" 227": logits[" 227"] + noise, " 226": logits[" 226"]}
    winner = max(shifted, key=shifted.get)
    console.print(f"rounding difference {noise:+.6f} -> greedy picks {winner!r}")
note("Temperature 0 picks the maximum. When two tokens are nearly tied, a rounding difference "
     "flips the winner, and every token after it is written on a different path.")

step("5. Why hosted models vary even at temperature 0")
causes = Table()
causes.add_column("cause")
causes.add_column("what happens")
for row in (
    ("batching", "Your request is computed alongside other users' requests. Batch size changes "
                 "the order of the arithmetic."),
    ("prompt caching", "A cached prefix is reused instead of recomputed (step 2 above)."),
    ("parallel kernels", "GPU reductions may combine partial sums in a different order each run."),
    ("mixture of experts", "Some models route each token to a few 'expert' sub-networks; "
                           "batch-dependent routing can change which experts run."),
    ("silent updates", "A provider may update the model, the hardware or the serving stack "
                       "behind the same model name."),
    ("sampling", "At temperature above 0 without a fixed seed, randomness is the design."),
):
    causes.add_row(*row)
console.print(causes)

step("6. The seed: making randomness repeatable")
for seed in (7, 7, 7, 8, 9):
    r = chat(northwind_messages(), temperature=0.9, seed=seed, max_tokens=8)
    console.print(f"  T=0.9 seed {seed}: {r.text!r}")
note("The seed fixes the random draws. Same seed, same draws, same text, provided the "
     "probabilities underneath are the same, which step 2 shows is not guaranteed.")

step("7. A finding record Hale cannot dismiss")
tags = {m["name"]: m for m in httpx.get(f"{host}/api/tags", timeout=10).json()["models"]}
version = httpx.get(f"{host}/api/version", timeout=10).json()["version"]
model = model_name(None)
plate_prompt = ("The gate camera recorded a partial plate 'KB 7?4 ?LR' where ? is unreadable. "
                "Registered plates: KB 714 FLR (R. Malhotra), KB 2209 MN (T. Reyes). Which "
                "plate matches? Reply with the plate only. Do not explain.")
settings = {"temperature": 0, "top_k": 40, "top_p": 0.9, "seed": 7, "num_ctx": 8192,
            "max_tokens": 60, "think": False}
first = chat(plate_prompt, **settings)
record = {
    "finding": "Partial plate KB 7?4 ?LR matches KB 714 FLR",
    "model": model,
    "model_digest": tags[model]["digest"],
    "server": f"ollama {version}",
    "settings": settings,
    "prompt_sha256": hashlib.sha256(plate_prompt.encode()).hexdigest(),
    "output": first.text,
    "output_sha256": hashlib.sha256(first.text.encode()).hexdigest(),
    "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
console.print_json(json.dumps(record))
replays = [chat(plate_prompt, **settings).text for _ in range(3)]
ok = all(r == first.text for r in replays)
reply("replayed 3 times from the record", "\n\n".join(replays),
      meta="REPRODUCED" if ok else "NOT REPRODUCED", style="green" if ok else "red")

finding("""
Hale is half right. On this workstation, at temperature 0, the same question can come back
with a different total, because the server's arithmetic depends on what it computed just
before. So LANTERN's findings will be short, checkable readings, never sums, and each one is
filed with a record: exact model digest, server version, settings, prompt hash and output.
The plate reading KB 714 FLR replays exactly from its record.

Varma signs the reply to Hale herself. "He asked for ordinary standards. He can have them."
""")
save_shot("06-temperature-zero-and-nondeterminism")

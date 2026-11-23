"""Chapter 16: what a call costs, what a stable prefix buys, and what breaks a cache."""

import statistics
import time
import uuid
from datetime import datetime

from lantern import case, chat, learn
from lantern.config import load_config, model_name, tier
from lantern.llm import Reply, cost_of
from lantern.ui import (
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    save_shot,
    step,
    your_turn,
)

chapter("16", "What it costs to ask", """
A request from headquarters, two lines long. Every force in the region wants LANTERN's message
classifier: about forty thousand intercepted messages a month between them. What would a year
cost, and would a hosted model, used only on synthetic training material, be cheaper or faster?

Varma passes it to you. "Not a guess," she says. "Measure what one call costs us here, then work
out what it would cost there. And tell me what makes the difference."
""")

LABELS = ["threat", "logistics", "personal"]
PER_YEAR = 40_000 * 12  # headquarters' figure: about forty thousand messages a month
HOSTED = "claude-haiku-5-5"  # the hosted model the estimate prices (config.yaml `prices:`)

GUIDE = case.read("sorting-guide.md")
messages = case.jsonl("messages.jsonl")
evidence("sorting-guide.md (first lines; the whole guide is the fixed part of every call)",
         "\n".join(GUIDE.splitlines()[:9]))


def ask(m: dict) -> str:
    return f"Message from {m['from']}: \"{m['text']}\""


def stable(m: dict) -> list[dict]:
    """The long fixed part first, the message last: every call starts with the same bytes."""
    return [{"role": "system", "content": GUIDE}, {"role": "user", "content": ask(m)}]


def varying(m: dict) -> list[dict]:
    """The same guide, behind a request ID and a timestamp: no two calls share a first line."""
    header = f"Request ID {uuid.uuid4()}. Received {datetime.now():%Y-%m-%d %H:%M:%S}.\n\n"
    return [{"role": "system", "content": header + GUIDE}, {"role": "user", "content": ask(m)}]


def parse(text: str) -> str:
    for word in text.lower().replace(".", " ").replace(":", " ").split():
        if word in LABELS:
            return word
    return "invalid"


def classify(layout, m: dict) -> Reply:
    return chat(layout(m), temperature=0, max_tokens=8, cache=True)


def hosted_estimate(prompt_tokens: int, output_tokens: int, read: int = 0, write: int = 0):
    """USD on the hosted model for one call of this size, from config.yaml's prices. An
    estimate: Qwen's token counts stand in for Claude's, which a different tokenizer makes."""
    return cost_of(Reply("", HOSTED, provider="anthropic", prompt_tokens=prompt_tokens,
                         output_tokens=output_tokens, cached_tokens=read,
                         cache_write_tokens=write))


local = tier() == "local"
model = model_name(None)

step("1. One call, counted")
p_tokens = learn.predict_number(
    f"The sorting guide is {len(GUIDE.split()):,} words. How many prompt tokens will one call "
    "carry, guide and message together?", unit="tokens")
first = classify(stable, messages[0])
# Ollama counts only the prompt tokens it had to process; a call that reuses a cached prefix
# reports fewer. A cold call (a fresh prefix) shows the full size.
cold = classify(varying, messages[0])
full_tokens = cold.prompt_tokens
t = Table(title=f"One call on {model} ({tier()} tier)")
for col in ("", "prompt tokens", "output tokens", "prompt processing s", "whole call s",
            "cost USD"):
    t.add_column(col, justify="left" if not col else "right")
for label, r in (("a fresh prefix", cold), ("the same prefix again", first)):
    t.add_row(label, f"{r.prompt_tokens:,}", str(r.output_tokens),
              f"{r.prompt_seconds:.3f}" if local else "not reported",
              f"{r.seconds:.2f}", f"{r.cost_usd:.6f}" if r.cost_usd is not None else "unknown")
console.print(t)
learn.reveal(p_tokens, actual=full_tokens, tolerance=0.3,
             why="A token is about three quarters of an English word, and the chat template adds "
             "a few more. Every one of them is sent, and on a hosted model billed, on every call.")
note("Locally a call costs nothing in money: it costs time, and the time is mostly the prompt.")
note(f"Ollama's `prompt_eval_count` counts only the tokens it had to process: the same prefix "
     f"again reported {first.prompt_tokens:,}, the fresh one {cold.prompt_tokens:,}." if local
     else "The hosted reply counts every input token, and the cached ones separately.")

step(f"2. Fixed part first: {len(messages)} messages, the guide always in front")
p_speed = learn.predict(
    "Ollama keeps the last prompt's KV cache and skips any prefix it has already processed. How "
    "much faster will prompt processing be when only the message changes?",
    ["about the same", "about 2 times", "3 to 20 times", "more than 20 times"])


def run(layout) -> dict:
    start = time.perf_counter()
    replies = [classify(layout, m) for m in messages]
    preds = [parse(r.text) for r in replies]
    return {
        "replies": replies,
        "secs": time.perf_counter() - start,
        "correct": sum(p == m["label"] for p, m in zip(preds, messages, strict=True)),
        "prompt_s": statistics.median(r.prompt_seconds for r in replies),
        "wall_s": statistics.median(r.seconds for r in replies),
        "tokens": statistics.median(r.prompt_tokens for r in replies),
    }


A = run(stable)

step(f"3. Something that changes, first: the same {len(messages)} calls behind a request ID")
p_hits = learn.predict(
    "Every call now starts with a new request ID and timestamp, and then the same guide. How many "
    f"of the {len(messages)} calls will reuse the cached guide?",
    ["none", "a few", "about half", "nearly all"])
B = run(varying)


COLD_S = statistics.median(r.prompt_seconds for r in B["replies"])  # every one of these is cold


def hit(r: Reply) -> bool:
    """Did this call reuse a cached prefix? Hosted: the provider says so. Local: Ollama
    processed under half the full prompt, or took under a quarter of a cold call's time."""
    if not local:
        return r.cached_tokens > 0
    return r.prompt_tokens < full_tokens / 2 or r.prompt_seconds < COLD_S / 4


for res in (A, B):
    res["hits"] = sum(hit(r) for r in res["replies"])

c = Table(title=f"The same {len(messages)} messages, two layouts ({model}, temperature 0)")
for col in ("layout", "cache hits", "prompt tokens processed (median)",
            "prompt processing s (median)", "whole call s (median)", "run s", "correct"):
    c.add_column(col, justify="left" if col == "layout" else "right")
for name, res in (("fixed part first", A), ("request ID first", B)):
    c.add_row(name, f"{res['hits']}/{len(messages)}", f"{res['tokens']:,.0f}",
              f"{res['prompt_s']:.3f}" if local else "not reported", f"{res['wall_s']:.2f}",
              f"{res['secs']:.0f}", f"{res['correct']}/{len(messages)}")
console.print(c)
speedup = B["prompt_s"] / A["prompt_s"] if A["prompt_s"] else 0.0
wall_speedup = B["wall_s"] / A["wall_s"] if A["wall_s"] else 0.0
learn.reveal(p_speed, answer=learn.bucket(speedup, [1.3, 2.9, 20]),
             why=f"Prompt processing: {speedup:.1f} times faster with the guide cached; the whole "
             f"call {wall_speedup:.1f} times. Only the message's few dozen tokens are new, so only "
             "they are processed. Generation, a few tokens here, does not change.")
learn.reveal(p_hits, answer=learn.bucket(B["hits"], [0, len(messages) // 4,
                                                     3 * len(messages) // 4]),
             why=f"{B['hits']} of {len(messages)}. A cache is a prefix match: the first character "
             "that differs ends the reuse, and the request ID is the first line. The guide behind "
             "it is identical every time and is still processed every time.")
note("Same guide, same messages, same answers: only the order of the bytes changed.")

step("4. What breaks a cache")


def shared_prefix(a: list[dict], b: list[dict]) -> int:
    """How many characters two requests share from the start (system turns joined)."""
    x = "".join(m["content"] for m in a)
    y = "".join(m["content"] for m in b)
    n = 0
    for ca, cb in zip(x, y, strict=False):
        if ca != cb:
            break
        n += 1
    return n


TOOLS = [
    {"name": "lookup_sender", "description": "Earlier messages from the same sender.",
     "parameters": {"type": "object", "properties": {"sender": {"type": "string"}},
                    "required": ["sender"]}},
    {"name": "lookup_case", "description": "Whether a name appears in an open case.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                    "required": ["name"]}},
]
probe = messages[1:7]
tool_runs = {}
for name, order in (("same order", lambda i: TOOLS),
                    ("order swapped each call", lambda i: TOOLS[::1 - 2 * (i % 2)])):
    rs = [chat(stable(m), tools=order(i), temperature=0, max_tokens=8, cache=True)
          for i, m in enumerate(probe)]
    tool_runs[name] = sum(hit(r) for r in rs[1:])  # the first call of each run sets the cache
b = Table(title="Two consecutive requests: where do they stop matching?")
for col in ("change", "characters shared", "of", "cache hits (live)"):
    b.add_column(col, justify="left" if col == "change" else "right")
pair_a = (stable(messages[0]), stable(messages[1]))
pair_b = (varying(messages[0]), varying(messages[1]))
total = len(GUIDE)
b.add_row("fixed part first, next message", f"{shared_prefix(*pair_a):,}", f"{total:,}",
          f"{A['hits']}/{len(messages)}")
b.add_row("request ID and time first", f"{shared_prefix(*pair_b):,}", f"{total:,}",
          f"{B['hits']}/{len(messages)}")
for name, hits in tool_runs.items():
    b.add_row(f"two tools, {name}", "", "", f"{hits}/{len(probe) - 1}")
console.print(b)
swapped, probes = tool_runs["order swapped each call"], len(probe) - 1
if swapped == probes and local:
    note(f"Swapping the two tools kept {swapped} of {probes} hits here: qwen3's chat template puts "
         "the tool list after the system text, so the guide in front stayed cached and only what "
         "followed it changed. Anthropic renders tools before the system prompt, so the same swap "
         "there invalidates the whole prefix. Sort tools by name and build them once, and the "
         "order never matters.")
else:
    note(f"Swapping the two tools kept {swapped} of {probes} hits. Where a provider renders tools "
         "ahead of the system text (Anthropic does), a reordered list changes the first bytes and "
         "nothing after is reused. Sort tools by name and build them once.")
note("Other silent breakers: a date in the system prompt, a dict serialised in a different "
     "order, a per-user line near the top, a changed model or a different thinking setting.")

step("5. A year of messages on a hosted model: an estimate, not a measurement")
p_year = learn.predict(
    f"With the guide cached, what share of the uncached cost would a year ({PER_YEAR:,} messages) "
    f"cost on {HOSTED}?",
    ["about the same", "about half", "about a quarter", "under a fifth"])
price = load_config()["prices"][HOSTED]
out_tokens = round(statistics.mean(r.output_tokens for r in A["replies"]))
suffix = max(full_tokens - round(statistics.median(r.prompt_tokens for r in A["replies"])), 1)
prefix = full_tokens - suffix
per_plain = hosted_estimate(full_tokens, out_tokens)
per_write = hosted_estimate(full_tokens, out_tokens, write=prefix)
per_read = hosted_estimate(full_tokens, out_tokens, read=prefix)
year_plain = per_plain * PER_YEAR
# Continuous traffic keeps a 5-minute cache warm: price one write per batch of 1,000 calls,
# which is conservative, and reads for the rest.
year_cached = (per_write + 999 * per_read) / 1000 * PER_YEAR
accuracy = A["correct"] / len(messages)
y = Table(title=f"Estimate for {HOSTED}: prices from config.yaml (checked {price['checked']}), "
          "token counts from this run's Qwen tokenizer")
for col in ("", "per call USD", f"per year USD ({PER_YEAR:,} calls)"):
    y.add_column(col, justify="left" if not col else "right")
y.add_row("no cache", f"{per_plain:.7f}", f"{year_plain:,.2f}")
y.add_row("cache write (first call)", f"{per_write:.7f}", "")
y.add_row("cache read (the rest)", f"{per_read:.7f}", "")
y.add_row("with cache", "", f"{year_cached:,.2f}")
y.add_row(f"per correct answer, at this run's {accuracy:.0%}",
          f"{year_cached / PER_YEAR / accuracy:.7f}" if accuracy else "no correct answers", "")
console.print(y)
share = year_cached / year_plain if year_plain else 0.0
learn.reveal(p_year, answer=learn.bucket(share, [0.8, 0.4, 0.2]),
             why=f"{share:.0%} of the uncached cost. The guide is {prefix:,} of the "
             f"{full_tokens:,} prompt tokens, and a cache read costs a tenth of the input price. "
             "What is left is the message, the output and the occasional write.")
under = hosted_estimate(100_000, out_tokens)
over = hosted_estimate(100_001, out_tokens)
note(f"Haiku's price tier: a 100,000-token request costs ${under:.4f}, a 100,001-token one "
     f"${over:.4f}. Packing a whole day's messages into one huge prompt can cost more, not less.")
note("Every number in this table is price arithmetic on token counts, not a hosted run. The "
     "hosted run is `make lesson N=16 TIER=hosted`, which reads cached tokens from the reply.")
if not local:
    spent = sum(r.cost_usd or 0 for r in A["replies"] + B["replies"])
    note(f"This hosted run's measured cost: ${spent:.6f} for {2 * len(messages)} calls.")

learn.record(
    model=model,
    full_prompt_tokens=full_tokens,
    prefix_tokens=prefix,
    calls_per_layout=len(messages),
    cache_hits_stable=A["hits"],
    cache_hits_varying=B["hits"],
    tool_order_hits_same=tool_runs["same order"],
    tool_order_hits_swapped=tool_runs["order swapped each call"],
    median_prompt_s_stable=round(A["prompt_s"], 4),
    median_prompt_s_varying=round(B["prompt_s"], 4),
    median_call_s_stable=round(A["wall_s"], 3),
    median_call_s_varying=round(B["wall_s"], 3),
    prompt_speedup=round(speedup, 1),
    correct_stable=A["correct"],
    correct_varying=B["correct"],
    est_usd_per_call_uncached=round(per_plain, 8),
    est_usd_per_call_cached=round(per_read, 8),
    est_usd_year_uncached=round(year_plain, 2),
    est_usd_year_cached=round(year_cached, 2),
)

your_turn(
    "16",
    check=[
        "In step 1, compare the prompt tokens of the fresh prefix with the same prefix again. "
        "What does Ollama's count leave out, and what would a hosted bill count?",
        "In step 3, the two layouts sent the same guide. Why did only one of them reuse it?",
        "In step 5, which line of the estimate would change if the model's tokenizer were "
        "different, and which would not?",
    ],
    exercises=[
        "In run.py, in stable(), add f\"Today is {datetime.now():%Y-%m-%d %H:%M:%S}.\" to the "
        "start of the system content. How many cache hits are left?",
        "In run.py, in varying(), move the header from the start of the system content to the "
        "start of the user turn. Do the hits come back?",
        "In run.py, cut the worked examples out of the guide you send (GUIDE.split('## Worked "
        "examples')[0]). What happens to the year estimate, and to the correct count?",
        "No edit: run LANTERN_MODEL=qwen3:4b make lesson N=16. Does the speedup grow or shrink "
        "with a larger model?",
    ],
)

finding(f"""
On LANTERN a call costs nothing but time, and most of the time is the prompt. With the sorting
guide first and the message last, {A['hits']} of {len(messages)} calls reused the cached guide and
prompt processing was {speedup:.1f} times faster. A request ID in the first line cut the reuse to
{B['hits']}, with the same guide and the same answers.

The hosted cost is price arithmetic until a hosted run measures it, and the screen says so.

Varma reads the line that says it is an estimate twice. "Then the next thing we prove," she says,
"is that LANTERN can take forty thousand messages without falling over."
""")
save_shot("16-prompt-caching-and-cost")

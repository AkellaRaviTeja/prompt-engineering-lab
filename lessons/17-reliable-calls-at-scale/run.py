"""Chapter 17: thousands of calls, and what goes wrong at that scale. Faults injected on purpose."""

import argparse
import random
import sys
import threading
import time
from pathlib import Path

from opentelemetry import context as otel_context

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate  # noqa: E402  (the seeded batch, beside this file)

from lantern import calllog, chat, learn, trace  # noqa: E402
from lantern.config import load_config, model_name, tier  # noqa: E402
from lantern.llm import Reply, cost_of  # noqa: E402
from lantern.retry import Transient  # noqa: E402
from lantern.ui import (  # noqa: E402
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

local = tier() == "local"
ap = argparse.ArgumentParser()
ap.add_argument("--batch", type=int, default=1200 if local else 120,
                help="messages in the main batch (smaller on the hosted tier: it is billed)")
ap.add_argument("--sweep", type=int, default=300 if local else 30,
                help="messages per concurrency level in the sweep")
ap.add_argument("--concurrency", type=int, default=2, help="concurrency of the main batch")
args, _ = ap.parse_known_args()

chapter("17", "Forty thousand messages", """
Headquarters sends a synthetic batch to test the classifier before it goes to every force:
invented messages in the shape of real intercepts, with the right label on each. Forty thousand
a month is the figure. "Last time a system like this went live," Varma says, "it ran beautifully
for an hour and then the first error stopped the whole queue. Nobody noticed until morning."

She wants three numbers before anything is switched on: how many messages a minute LANTERN can
sort, how long the slowest ones take, and what happens when calls start to fail.
""")

MINE = learn.mine()
run_batch = MINE.run_batch if MINE else None
if run_batch is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "practice"))
    from solution import run_batch  # noqa: E402  (the lesson's runner; --mine uses yours)

MODEL = model_name("small")
VERSION = "classify-message@v1"
LABELS = ["threat", "logistics", "personal"]
SYSTEM = """Classify a text message from a company executive's work phone.
Labels:
- threat: intimidation, pressure or warnings aimed at the recipient
- logistics: work operations, schedules, deliveries, invoices
- personal: family, friends, health, private life
Answer with exactly one word: threat, logistics or personal."""
TIMEOUT = 3.0  # seconds for one attempt; step 1 shows why
RETRIES, BASE, CAP = 3, 0.25, 4.0

batch = generate.messages(args.batch)
evidence(f"synthetic batch: {len(batch):,} messages, seed {generate.SEED} (first 3)", "\n".join(
    f"{m['id']}  {m['time']}  {m['from']:<18} {m['text']}" for m in batch[:3]))


def prompt(m: dict) -> list[dict]:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Message from {m['from']}: \"{m['text']}\""}]


def parse(text: str) -> str:
    for word in text.lower().replace(".", " ").replace(":", " ").split():
        if word in LABELS:
            return word
    return "invalid"


def model_call(messages: list[dict], **kw) -> Reply:
    """One attempt, no retries inside: the batch runner owns retries. lantern.chat turns a
    Transient it will not retry into SystemExit; give the runner back the Transient."""
    try:
        return chat(messages, model=MODEL, temperature=0, max_tokens=6, retries=0,
                    prompt_version=VERSION, **kw)
    except SystemExit as e:
        if isinstance(e.__cause__, Transient):
            raise e.__cause__ from None
        raise


def in_this_trace(fn):
    """Worker threads do not inherit the trace context: carry it over, so each chat span nests
    under the batch span."""
    ctx = otel_context.get_current()

    def call(messages, **kw):
        token = otel_context.attach(ctx)
        try:
            return fn(messages, **kw)
        finally:
            otel_context.detach(token)

    return call


class Faults:
    """Seeded fault injection: a set share of attempts fail as a 429, a 503, or a stuck call.

    The draw depends only on the message and the attempt number, so the same faults hit the same
    calls whatever order the threads run in. A stuck call hangs until the caller's timeout and
    then fails, which is what httpx does when a server never answers.
    """

    def __init__(self, fn, *, r429: float, r503: float, stuck: float, seed: int = 17):
        self.fn, self.r429, self.r503, self.stuck, self.seed = fn, r429, r503, stuck, seed
        self.lock = threading.Lock()
        self.tries: dict[str, int] = {}
        self.count = {"429": 0, "503": 0, "stuck": 0}

    def __call__(self, messages, *, timeout: float, **kw):
        key = messages[-1]["content"]
        with self.lock:
            n = self.tries[key] = self.tries.get(key, 0) + 1
        x = random.Random(f"{self.seed}:{key}:{n}").random()
        if x < self.r429:
            kind = "429"
        elif x < self.r429 + self.r503:
            kind = "503"
        elif x < self.r429 + self.r503 + self.stuck:
            kind = "stuck"
        else:
            return self.fn(messages, timeout=timeout, **kw)
        with self.lock:
            self.count[kind] += 1
        if kind == "stuck":
            time.sleep(timeout)
            raise Transient(f"no answer within {timeout:.0f}s (injected stuck call)")
        raise Transient(f"HTTP {kind} (injected)")


def pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile: p=50 is the median, p=95 the value 95% of calls are under."""
    if not values:
        return 0.0
    s = sorted(values)
    return s[max(0, min(len(s) - 1, round(p / 100 * len(s) + 0.5) - 1))]


def logged_since(mark: int) -> list[dict]:
    """This chapter's call-log records written after `mark` lines."""
    return [r for r in calllog.read()[mark:] if r.get("chapter") == "17"
            and r.get("lantern.prompt.version") == VERSION]


def go(items, *, concurrency: int, fn, name: str, **kw) -> dict:
    """Run one batch inside a span; read its numbers back from the call log."""
    mark = len(calllog.read())
    events: list[dict] = []
    with trace.span(name, **{"lantern.batch.size": len(items),
                             "lantern.batch.concurrency": concurrency}) as sp:
        start = time.perf_counter()
        results = run_batch(items, chat=in_this_trace(fn), prompt=prompt,
                            concurrency=concurrency, timeout=TIMEOUT, retries=kw.pop("retries",
                            RETRIES), base=BASE, cap=CAP, log=events.append, **kw)
        wall = time.perf_counter() - start
        trace_id = f"0x{sp.get_span_context().trace_id:032x}"
    log = logged_since(mark)
    from_log = len(log) == sum(r["ok"] for r in results) and bool(log)
    call_secs = ([r["lantern.latency_s"] for r in log] if from_log
                 else [r["reply"].seconds for r in results if r["ok"]])
    ok = [r for r in results if r["ok"]]
    correct = sum(parse(r["reply"].text) == m["label"]
                  for r, m in zip(results, items, strict=True) if r["ok"])
    return {
        "results": results, "events": events, "wall": wall, "log": log, "from_log": from_log,
        "n": len(items), "ok": len(ok), "failed": len(items) - len(ok),
        "per_min": len(ok) / wall * 60 if wall else 0.0,
        "p50": pct(call_secs, 50), "p95": pct(call_secs, 95),
        "item_p50": pct([r["seconds"] for r in ok], 50),
        "item_p95": pct([r["seconds"] for r in ok], 95),
        "retries": sum(e["outcome"] == "retry" for e in events),
        "retried_items": sum(r["attempts"] > 1 for r in results),
        "correct": correct, "trace_id": trace_id,
    }


step("1. Warm up, and choose the timeout")
warm = [model_call(prompt(m), timeout=60) for m in batch[:20]]
warm_secs = [r.seconds for r in warm[1:]]
note(f"{MODEL}: the first call took {warm[0].seconds:.2f}s (it may load the model); the next "
     f"{len(warm_secs)} took {pct(warm_secs, 50):.2f}s at the median and {max(warm_secs):.2f}s at "
     "most.")
note(f"Timeout per attempt: {TIMEOUT:.0f}s. Long enough that a healthy call is never cut off, "
     "short enough that a stuck one does not hold a worker for minutes. config.yaml's 300s is "
     "for a cold 4B model on a CPU, not for a warm batch.")

step(f"2. Throughput at concurrency 1, 2 and 4 ({args.sweep} messages each, no faults)")
p_conc = learn.predict(
    "Going from one call at a time to four at once, how will messages per minute change?",
    ["about 4 times as many", "about 2 times as many", "about the same", "fewer"])
sweep_items = batch[: args.sweep]
sweep = {c: go(sweep_items, concurrency=c, fn=model_call, name=f"sweep c={c}") for c in (1, 2, 4)}
s = Table(title=f"{MODEL}, {args.sweep} messages per row, read back from .progress/calls.jsonl")
for col in ("concurrency", "messages/min", "call p50 s", "call p95 s", "failed", "correct"):
    s.add_column(col, justify="right")
for c, res in sweep.items():
    s.add_row(str(c), f"{res['per_min']:,.0f}", f"{res['p50']:.3f}", f"{res['p95']:.3f}",
              str(res["failed"]), f"{res['correct']}/{res['n']}")
console.print(s)
gain = sweep[4]["per_min"] / sweep[1]["per_min"] if sweep[1]["per_min"] else 0.0
learn.reveal(p_conc, answer=learn.bucket(-gain, [-3.0, -1.5, -0.9]),
             why=f"Four at once gave {gain:.2f} times the throughput of one. "
             + ("Ollama here runs one request at a time (one parallel slot): extra concurrency "
                "only queues at the server, so each call's latency grows while throughput "
                "barely moves. Concurrency helps only up to the server's own parallelism."
                if local else "A hosted API serves many requests at once, up to your rate "
                "limit, so concurrency is where its throughput comes from."))
if not all(r["from_log"] for r in sweep.values()):
    note("The call log is off (LANTERN_CALL_LOG is empty): these numbers come from the replies.")

step(f"3. The whole batch, {len(batch):,} messages at concurrency {args.concurrency}, with faults")
FAULTS = {"r429": 0.04, "r503": 0.03, "stuck": 0.01}
note(f"Injected, seeded: {FAULTS['r429']:.0%} of attempts get a 429, {FAULTS['r503']:.0%} a 503, "
     f"{FAULTS['stuck']:.0%} hang until the {TIMEOUT:.0f}s timeout cuts them off.")
p_fail = learn.predict(
    f"With {RETRIES} retries, exponential backoff and full jitter, how many of the "
    f"{len(batch):,} messages will still fail?",
    ["none", "1 to 10", "11 to 50", "more than 50"])
faulty = Faults(model_call, **FAULTS)
budget = max(1, len(batch) // 5)
main = go(batch, concurrency=args.concurrency, fn=faulty, name="batch with faults",
          retry_budget=budget)
m = Table(title=f"{len(batch):,} messages, {MODEL}, concurrency {args.concurrency}, timeout "
          f"{TIMEOUT:.0f}s, {RETRIES} retries, budget {budget}")
for col in ("", "count"):
    m.add_column(col, justify="left" if not col else "right")
injected = sum(faulty.count.values())
m.add_row("faults injected (429 / 503 / stuck)",
          f"{injected} ({faulty.count['429']} / {faulty.count['503']} / {faulty.count['stuck']})")
m.add_row("messages that needed a retry", str(main["retried_items"]))
m.add_row("retries spent (of the budget)", f"{main['retries']} of {budget}")
m.add_row("messages that failed in the end", str(main["failed"]))
m.add_row("messages per minute", f"{main['per_min']:,.0f}")
m.add_row("model call p50 / p95 s (from the call log)", f"{main['p50']:.3f} / {main['p95']:.3f}")
m.add_row("whole message p50 / p95 s (waits included)",
          f"{main['item_p50']:.3f} / {main['item_p95']:.3f}")
m.add_row("agreement with the gold labels", f"{main['correct']}/{len(batch):,}")
console.print(m)
learn.reveal(p_fail, answer=learn.bucket(main["failed"], [0, 10, 50]),
             why=f"{main['failed']} failed. {main['retried_items']} messages hit at least one "
             "fault; without retries every one of them would have failed. A fault has to strike "
             f"the same message {RETRIES + 1} times in a row to beat the retries.")
note("The faults show in the tail, not the middle: the median message barely moved, the 95th "
     "percentile carries the backoff waits and the cut-off stuck calls.")

step("4. An outage: the retry budget")
p_budget = learn.predict(
    "Now 70% of attempts fail, as in a real outage. With a retry budget of 20 for 100 messages, "
    "how many attempts will the batch make in total?",
    ["about 100", "about 120", "about 250", "about 400"])
outage = Faults(model_call, r429=0.4, r503=0.3, stuck=0.0, seed=4)
storm = go(batch[:100], concurrency=args.concurrency, fn=outage, name="outage with budget",
           retry_budget=20)
attempts = sum(r["attempts"] for r in storm["results"])
learn.reveal(p_budget, answer=learn.bucket(attempts, [110, 180, 320]),
             why=f"{attempts} attempts, {storm['failed']} messages failed. Without a budget the "
             f"same outage could make up to {100 * (RETRIES + 1)}: every retry is more load on a "
             "service that is already failing. The budget turns an outage into a short list of "
             "messages to run again later, instead of a retry storm.")
note(f"70% of attempts failing, 100 messages, retry budget 20: {attempts} attempts in all, "
     f"{storm['failed']} messages failed and are listed to run again. Without the budget the same "
     f"outage could have made up to {100 * (RETRIES + 1)} attempts on a service already failing.")

step("5. What the log says")
logged = main["log"] + [r for res in sweep.values() for r in res["log"]] + storm["log"]
tokens_in = sum(r["gen_ai.usage.input_tokens"] for r in logged)
tokens_out = sum(r["gen_ai.usage.output_tokens"] for r in logged)
spans = 0
if trace.PATH.exists():
    for line in trace.PATH.read_text(encoding="utf-8").splitlines():
        if main["trace_id"] in line and '"chat ' in line:
            spans += 1
per_msg_in = tokens_in / len(logged) if logged else 0
per_msg_out = tokens_out / len(logged) if logged else 0
hosted_model = load_config()["hosted"]["anthropic"]["models"]["small"]
est = cost_of(Reply("", hosted_model, provider="anthropic", prompt_tokens=round(per_msg_in),
                    output_tokens=round(per_msg_out)))
month_minutes = 40_000 / main["per_min"] if main["per_min"] else 0.0
g = Table(title="Read back from .progress/calls.jsonl and .progress/traces.jsonl")
for col in ("", "value"):
    g.add_column(col, justify="left" if not col else "right")
g.add_row("calls logged this run (prompt version " + VERSION + ")", f"{len(logged):,}")
g.add_row("input / output tokens", f"{tokens_in:,} / {tokens_out:,}")
g.add_row("cost logged (USD)", f"{sum(r['lantern.cost_usd'] or 0 for r in logged):.4f}")
g.add_row("chat spans under the 'batch with faults' trace", f"{spans:,}")
g.add_row(f"40,000 messages at {main['per_min']:,.0f}/min (extrapolated)",
          f"{month_minutes / 60:.1f} hours")
g.add_row(f"40,000 messages on {hosted_model}, estimated from these token counts",
          f"${est * 40_000:.2f}" if est is not None else "unpriced")
console.print(g)
note("Only successful calls reach the call log: a failed attempt never returns a reply. The "
     "runner's own log events count the failures; the call log counts the work done.")

learn.record(
    model=MODEL,
    batch=len(batch),
    sweep=args.sweep,
    concurrency=args.concurrency,
    per_min_c1=round(sweep[1]["per_min"], 1),
    per_min_c2=round(sweep[2]["per_min"], 1),
    per_min_c4=round(sweep[4]["per_min"], 1),
    p50_c1=round(sweep[1]["p50"], 3),
    p95_c1=round(sweep[1]["p95"], 3),
    p95_c4=round(sweep[4]["p95"], 3),
    faults_injected=injected,
    retried_items=main["retried_items"],
    retries_spent=main["retries"],
    failed=main["failed"],
    per_min_batch=round(main["per_min"], 1),
    call_p95_batch=round(main["p95"], 3),
    item_p95_batch=round(main["item_p95"], 3),
    correct=main["correct"],
    outage_attempts=attempts,
    outage_failed=storm["failed"],
    logged_calls=len(logged),
    spans=spans,
    mine=bool(MINE),
)

your_turn(
    "17",
    check=[
        "In step 2, compare call p95 at concurrency 1 and 4. Where did the extra time go?",
        "In step 3, compare the model call p95 with the whole message p95. What is in the gap?",
        "In step 4, how many messages would you run again tomorrow, and how do you find them?",
    ],
    exercises=[
        "In run.py, set RETRIES to 0 and rerun. How many messages fail in step 3?",
        "In run.py, set BASE to 0 (no backoff) and give the outage a budget of 1,000. Count the "
        "attempts in step 4.",
        "In run.py, set TIMEOUT to 0.05. What happens to healthy calls?",
        "No edit: make lesson N=17 ARGS=\"--concurrency 4\". Does the batch finish sooner?",
    ],
)

right_share = main["correct"] / len(batch)
verdict = ("wrong most of the time" if right_share < 0.5 else
           "wrong more often than a court would accept" if right_share < 0.9 else
           "right nine times in ten or better")
finding(f"""
On this machine LANTERN sorts about {main['per_min']:,.0f} messages a minute on {MODEL}, with
faults, so a month of forty thousand is about {month_minutes / 60:.1f} hours of work. Of {injected}
attempts made to fail on purpose, {main['failed']} messages were lost, and the budget held an outage
to {attempts} attempts. Every call is in the log with its prompt version, model, tokens and latency.

The answers are another matter: {main['correct']:,} of {len(batch):,} agree with the labels.
Varma reads the log, not the summary. "Every call, with its version and its time," she says.
"Good. Hale will ask for exactly that. And he will ask why we ran a model that is {verdict}.
Before anything goes to court, we prove the pipeline is right, not just that it runs."
""")
save_shot("17-reliable-calls-at-scale")

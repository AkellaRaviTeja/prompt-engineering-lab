# Chapter 17: Forty thousand messages

**Concept:** reliable calls at scale: throughput, tail latency, timeouts, retries with backoff
and jitter, a retry budget, and a log and a trace of every call.

## The scene

Headquarters sends a synthetic batch to test the classifier before it goes to every force:
invented messages in the shape of real intercepts, with the right label on each. Forty thousand
a month is the figure. "Last time a system like this went live," Varma says, "it ran beautifully
for an hour and then the first error stopped the whole queue. Nobody noticed until morning."

She wants three numbers before anything is switched on: how many messages a minute LANTERN can
sort, how long the slowest ones take, and what happens when calls start to fail.

The batch is made by [`generate.py`](generate.py), seeded, so every run sorts the same messages.

## The concept

Forty-eight messages hide every problem this chapter is about. At a few thousand, the problems
are the point:

- **Throughput**: messages per minute. It decides whether a month's work takes an afternoon or a
  week.
- **Tail latency**: the 95th percentile (p95), the time that 95 messages in 100 finish within.
  The median says what a typical message costs; the tail says what the queue behind it feels.
- **Failures**: at scale, some calls fail. A rate limit (HTTP 429), an overloaded server (503), a
  call that never answers. One unhandled failure must not stop the batch, and a thousand retries
  must not turn a short outage into a long one.

![Batch runner](../../docs/diagrams/17-batch-runner.svg)

The runner in the diagram is the chapter's exercise. Five parts, each answering one failure:

| Part | Without it |
|---|---|
| Bounded concurrency | Either one call at a time, or as many as the server will queue |
| A timeout per attempt | One stuck call holds a worker for minutes |
| Retries on `Transient` only | A blip fails a message; or a bad request is sent again and again |
| Exponential backoff with full jitter | Every worker that failed together retries together |
| A retry budget for the batch | An outage multiplies the load on the service that is failing |

## How it works

**The batch.** `generate.messages(n)` fills thirty templates (logistics, personal, threat) with
seeded details: ships, piers, invoice numbers, days. Each message has a gold label, so the batch
also measures agreement.

**One attempt.** `chat(..., retries=0, timeout=3)`: the runner owns retries, so the client's own
are off. `lantern.chat` measures every call on the wall clock, logs it to `.progress/calls.jsonl`
with its prompt version (`classify-message@v1`), model, tokens, cost and latency
(`lantern.calllog`), and traces it as an OpenTelemetry span with GenAI attributes in
`.progress/traces.jsonl` (`lantern.trace`).

**Retries.** `lantern.retry.backoff(n, base, cap)` is full jitter: a random wait between 0 and
`min(cap, base * 2**n)`. With `base=0.25` and `cap=4`, the first retry waits up to 0.25 s, the
third up to 1 s. A `retry-after` hint from the provider is a floor on the wait.

**Faults, on purpose.** `Faults` wraps the model call. For a seeded share of attempts it raises
`Transient("HTTP 429")` or `Transient("HTTP 503")` instead of calling the model, or it hangs until
the timeout and then fails, as httpx does when a server never answers. The draw depends only on
the message and the attempt number, so every run injects the same faults.

**Reading it back.** Each batch runs inside `trace.span(...)`. Worker threads do not inherit the
trace context, so the chapter carries it over (`in_this_trace`) and each chat span nests under its
batch. The numbers in steps 2, 3 and 5 are read back from the call log, not kept in memory: the
log is what an operator would have.

```python
results = run_batch(batch, chat=faulty, prompt=prompt, concurrency=2, timeout=3.0,
                    retries=3, base=0.25, cap=4.0, retry_budget=len(batch) // 5)
```

## The nuances

**1. Concurrency helps only up to the server's parallelism.** NUANCE1

**2. Report the tail.** NUANCE2

**3. Retry only what can succeed next time.** A 429, a 5xx, a timeout or a dropped connection may
succeed a moment later. A 400 (a schema the provider rejects, a prompt too long) fails the same
way every time; retrying it burns quota. `lantern.retry.Transient` marks the first kind, and the
runner fails the second at once.

**4. Jitter is what makes backoff work.** NUANCE4

**5. A budget turns an outage into a list.** NUANCE5

**6. Set the timeout from the measured tail.** NUANCE6

**7. Only successful calls reach the call log.** A failed attempt never produces a reply, so the
call log counts the work done and the runner's own events count the failures. Read both. Every
logged call carries its prompt version, so a change of prompt shows up as a new version in the
log, not as a mystery in the numbers.

**8. Extrapolate with care.** NUANCE8

## Run it

```bash
make lesson N=17                          # the full run
make lesson N=17 ARGS="--batch 200"       # a quick run
make lesson N=17 ARGS="--concurrency 4"   # the main batch at another concurrency
make lesson N=17 ARGS=--mine              # on the runner you wrote
```

RUNTIME

## What you should see

![Chapter 17 terminal output](../../docs/screenshots/17-reliable-calls-at-scale.png)

SEE

## On a hosted model

```bash
make lesson N=17 TIER=hosted            # needs ANTHROPIC_API_KEY in .env; 120 messages by default
make lesson N=17 TIER=hosted REPLAY=1   # from a recorded run, once one is committed
```

On the hosted tier the batch is smaller by default (`--batch 120 --sweep 30`): every call is
billed. The model is `claude-haiku-5-5`. The runner is the same; what differs is the server. A
hosted API runs many requests at once, up to the account's rate limit, so concurrency is where its
throughput comes from, and a real 429 carries a `retry-after` header that `lantern.cloud` passes
to the runner as the floor on its wait. The Anthropic SDK's own retries are turned off
(`max_retries=0`) so that every attempt is counted here. Claude does not take `temperature` or
`seed`; they are not sent and are reported once on the console.

HOSTED

## Try this

1. Set `RETRIES = 0` and rerun. How many messages fail in step 3, and which faults caused them?
2. Set `BASE = 0` and give the outage a budget of 1,000. Count the attempts in step 4.
3. Set `TIMEOUT = 0.05`. What happens to healthy calls, and to the retry budget?
4. Run `make lesson N=17 ARGS="--concurrency 4"`. Does the batch finish sooner? Compare the call
   p95 with step 2.
5. Open `.progress/calls.jsonl` and find the slowest call of the run. Then find its span in
   `.progress/traces.jsonl` by its time, and read which batch it belonged to.

## Master it

After this chapter you can measure a batch in messages per minute and p50 and p95 latency, read
the numbers back from a call log, say why concurrency stops helping, and write a runner that
survives rate limits, server errors and stuck calls without turning an outage into a storm.

**Predict, then see.** `make lesson N=17` stops three times to ask: how throughput changes from
one call at a time to four, how many messages still fail after retries, and how many attempts an
outage costs with a retry budget. Each answer is checked against your own run. Add
`ARGS=--no-predict` to watch without stopping.

**Build it.** Write `run_batch()` in [`practice/exercise.py`](practice/exercise.py): bounded
concurrency, a timeout, retries with backoff and full jitter, a retry budget and a log event per
attempt. run.py uses it in place of its own with `--mine`.

```bash
make exercise N=17             # 9 offline tests, scripted model, no Ollama needed
make hint N=17                 # one hint at a time
make solution N=17             # the reference, once you have tried
make lesson N=17 ARGS=--mine   # the whole batch, faults and all, on your runner
```

**Check yourself.** `make quiz N=17`: six questions, each with the reason behind the answer.

**Break it.** `make challenge N=17` checks your latest run against three targets: your runner on
the real batch, losing no more than five messages; no retries, so the faults get through; and a
retry storm in the outage, three times the attempts the budget allowed.

`make progress` shows every chapter.

## What the evidence now shows

EVIDENCE

**Next:** [Chapter 18: Proven, not demonstrated](../18-evals-with-promptfoo/README.md)

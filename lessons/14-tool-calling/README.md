# Chapter 14: Ask the ledger

**Concept:** tool calling. The model asks your code for a fact through a declared function with a
JSON schema, your code validates and runs it, and the result goes back to the model: first with a
protocol you write in the prompt, then with the API's native tool calling.

## The scene

Okafor reads LANTERN's answer twice, then puts his finger on one line. "That amount for NW-0388.
Where did it come from?" Nowhere. You asked LANTERN about the ledger, and it answered the way a
witness answers about something they half remember: confidently, in the right shape, and wrong.

Varma does not raise her voice. "It does not read the ledger. It remembers something like the
ledger. From now on, when it needs a fact, it asks for the row, and I want to see what it asked
for."

Headquarters will change the model next quarter; the ledger will not change. You give LANTERN
three ways to look things up, and you write down every request it makes.

## The concept

A model cannot read a file, query a database or check a clock. It can only write text. **Tool
calling** turns that limit into a protocol: you describe functions to the model (a name, a
description, a JSON schema for the arguments), the model replies with a request to call one, your
code runs it, and the result goes back into the conversation for the next turn.

The model never runs anything. It asks. Your code decides whether the request is well formed,
whether to run it, and what to send back. That split is the whole design, and every safeguard in
this chapter and the next lives on your side of it.

There are two ways to build the protocol:

| | By hand | Native |
|---|---|---|
| Where the tools are described | In the system prompt, as text | In the API's `tools` field |
| How a call comes back | JSON somewhere in the reply text, which you find and parse | A structured `tool_calls` list, separate from the text |
| Several calls at once | Only if your prompt and parser allow it | A reply can carry several, each with an id |
| How the result goes back | A user turn you format | A `tool` turn carrying the call's id |
| What the model was trained on | Your format, never | The provider's format |

Teams use native tool calling: Ollama's `tools` field here, and on the hosted tier Anthropic's
`tool_use` and `tool_result` blocks. Building it by hand first shows what the native version does
for you, and the chapter measures the difference on the same questions.

## How it works

![The tool loop](../../docs/diagrams/14-tool-loop.svg)

Each tool is a plain function over a case file, with a schema:

```python
def ledger_lookup(reference: str) -> dict:
    for row in LEDGER:
        if row["reference"] == reference.strip().upper():
            return {k: row[k] for k in ("date", "payee", "description", "amount_kbd", "reference")}
    raise LookupError(f"no ledger row with reference {reference}")

TOOLS = [{"name": "ledger_lookup",
          "description": "Look up one payment in Halcyon's seized ledger by its reference.",
          "parameters": {"type": "object",
                         "properties": {"reference": {"type": "string",
                                                      "pattern": r"^[A-Z]{2,3}-\d{4}$"}},
                         "required": ["reference"], "additionalProperties": False}}]
```

The native loop, in full (`native()` in [run.py](run.py)):

```python
for turn in range(1, max_steps + 1):              # the step cap
    r = chat(messages, tools=tools)
    if not r.tool_calls:
        return r.text                              # no calls: this is the answer
    messages.append({"role": "assistant", "content": r.text,
                     "tool_calls": [{"id": i, "function": {"name": c.name,
                                                           "arguments": c.arguments}} ...]})
    for call_id, c in zip(ids, r.tool_calls):
        if c.name not in functions:      result = {"error": f"no tool named {c.name!r}"}
        elif problems := validate(c.arguments, schemas[c.name]):
                                         result = {"error": "invalid arguments: ..."}
        else:
            fn = functions[c.name]
            try:                         result = fn(**c.arguments)
            except LookupError as e:     result = {"error": str(e)}
        messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)})
```

The hand-built version puts the schemas in the system prompt and asks for
`{"tool": ..., "arguments": ...}` or `{"answer": ...}` as the whole reply, one tool per reply.
`first_json()` finds the first JSON object in whatever comes back; anything else is a parse
failure, and the loop tells the model so and tries again.

The run asks six questions about the case files three ways, at temperature 0: from memory with no
tools, with the hand-built protocol, and with native tool calling.

## The nuances

**1. A tool does not make the model use it.** In this run native tool calling answered three of
six questions, and on four of them it made no call at all. Question 1 came back as "cannot be
determined without additional information", with the tool that holds the answer one field away.
A small model decides whether to call a tool the same way it decides anything else: by what looks
likely. Count the calls, not only the answers.

**2. Native is not automatically better than hand-built.** The hand-built protocol answered four
of six here, against native's three, because its system prompt says "reply with a request or an
answer" and the model mostly obeyed. It paid for it: 12 requests, 4 replies that were not JSON at
all, and 18 model calls against native's 8. Native calls are structured by the API, so none failed
to parse; that guarantee is about shape, not about judgement. Measure both on your own questions
before you pick.

**3. Recall is worse than either, and sounds just as sure.** From memory LANTERN got none of six
right, with amounts in rupees, pounds and dollars for a ledger kept in KBD, and a
"debit of 1,200" against NW-0500, which does not exist. Every one was in the right shape. That is
the reason for tools: the answer comes from a row you can show in court.

**4. Validate arguments before the tool runs.** The schema is a contract, and the model breaks it:
"nw 388" in lower case, `ref` for `reference`, the number 388 for a string. Step 6 rejects each
one before it touches the ledger and sends the reason back. A tool that runs on bad arguments
either crashes or, worse, answers a question nobody asked.

**5. Errors are results.** NW-0500 is not in the ledger. The tool raises, the loop turns that into
`{"error": ...}` and sends it back as the tool's result, and the model says the record is not
available. A tool that returns an empty answer instead invites the model to fill the gap: try it
(Try this 2).

**6. Cap the steps.** A loop that asks the model "anything else?" until it stops can run forever on
a model that keeps asking for the same row. The cap here is five calls per question; this run hit
it zero times, which is what a cap is for: it is not supposed to fire, and you want to know when
it does.

**7. Parallel calls are a capability, not a promise.** Question 5 needs two rows. The API lets one
reply carry several calls, and a larger model often uses that; qwen3:1.7b made none in this run,
by hand or native. Code the loop for several calls per reply anyway, and return every result before
the next model turn.

## Run it

```bash
make lesson N=14
make lesson N=14 ARGS=--mine     # the native step on your own run_tools (see Master it)
```

About 32 model calls on `qwen3:1.7b` (6 from memory, 18 by hand, 8 native). Under a minute on
an Apple M1 Pro with 16 GB when the model is already loaded.

## What you should see

![Chapter 14 terminal output](../../docs/screenshots/14-tool-calling.png)

A real run on `qwen3:1.7b`, local tier, Apple M1 Pro 16 GB, temperature 0:

| measure | recall | by hand | native |
|---|---|---|---|
| answers right (of 6) | 0 | 4 | 3 |
| tool requests | 0 | 12 | 2 |
| requests usable (parsed and valid) | | 8 | 2 |
| replies that were not a request or an answer | | 4 | 0 |
| model calls (turns) | 6 | 18 | 8 |
| questions cut off at the step cap | | 0 | 0 |

- **Recall** invents every answer, in the right shape: amounts in three currencies and a debit
  against NW-0500, a reference that is not in the ledger.
- **By hand** gets four right and costs the most: a third of its replies were prose, not the JSON
  request the prompt asked for, and each one cost a turn to correct.
- **Native** never fails to parse, but calls a tool on only two of six questions; on the other four
  it answers without looking, and two of those answers are wrong.
- **Step 6** shows three bad argument sets rejected before they ran, and NW-0500's "not found"
  going back to the model as a result.

Your numbers will differ in detail. The pattern to look for is the gap between "can call a tool"
and "does call it".

## On a hosted model

```bash
make lesson N=14 TIER=hosted     # needs ANTHROPIC_API_KEY in .env
make lesson N=14 TIER=hosted REPLAY=1   # from a recorded run, once one is committed
```

The native step uses Anthropic's native tool use: each tool becomes a `tools` entry with an
`input_schema`, each call comes back as a `tool_use` block with an id, and each result goes back
as a `tool_result` block carrying that id (see `anthropic_request` in `src/lantern/cloud.py`).
The hand-built step sends the same prompt protocol as text. Claude does not take `temperature`
(current models reject sampling settings) or `seed`, so the run's `temperature=0` is not sent and
is reported once on the console; repeated hosted runs may differ.

| Measure | Local: qwen3:1.7b, Ollama, Apple M1 Pro 16 GB | Hosted: claude-haiku-5-5 |
|---|---|---|
| answers right from memory (of 6) | 0 | not run |
| answers right, by hand (of 6) | 4 | not run |
| answers right, native (of 6) | 3 | not run |
| native tool calls made | 2 | not run |
| model calls, native | 8 | not run |

Live hosted numbers are not run: this lab has no hosted key, and no number here is estimated.

What the hosted run will test: whether native calling overtakes the hand-built protocol once the
model reliably decides to call a tool (the four questions native answered without looking are the
likeliest small-model effect), and whether a larger model issues both lookups for question 5 in
one reply. That recall invents ledger rows and that validation and error results are needed
should hold on both.

## Try this

1. Set `MAX_STEPS = 2` in run.py. Which questions are cut off, and which approach suffers more?
2. In `ledger_lookup`, return `{}` instead of raising `LookupError`. What does LANTERN now say
   about NW-0500?
3. Delete the `pattern` from the `reference` schema and ask question 1 with "nw 388" written in
   lower case. Does the call still reach the ledger, and does it find the row?
4. Run with `LANTERN_MODEL=qwen3:0.6b` and with `LANTERN_MODEL=qwen3:4b`. Which approach holds up
   on the small model?

## Master it

After this chapter you can follow a tool call message by message, write the tool loop with
validation, errors returned to the model and a step cap, and measure a hand-built protocol
against native tool calling.

**Predict, then see.** `make lesson N=14` stops four times to ask: how many questions LANTERN
gets right from memory, how many hand-written requests are usable, how native tool calling fetches
two rows at once, and how many model calls the native run needs. Each answer is checked against
your own run. Add `ARGS=--no-predict` to watch without stopping.

**Build it.** Write `validate()` and `run_tools()` in
[`practice/exercise.py`](practice/exercise.py): the whole loop the native step runs.

```bash
make exercise N=14             # 8 offline tests, scripted model, no Ollama needed
make hint N=14                 # one hint at a time
make solution N=14             # the reference, once you have tried
make lesson N=14 ARGS=--mine   # the six questions through your run_tools()
```

**Check yourself.** `make quiz N=14`: six questions, each with the reason behind the answer.

**Break it.** `make challenge N=14` checks your latest run against three targets: your loop
answering five of six natively; a tool that hides "not found", so LANTERN invents an amount for
NW-0500; and a hand-built protocol with parallel requests that needs no more turns than native.

`make progress` shows every chapter.

## What the evidence now shows

LANTERN no longer recalls the ledger; it asks for the row, and every request is on the record.
From memory it got none of the six questions right. With native tool calling it answered three
from the case files, and the hand-built protocol four, at more than twice the model calls.
Northwind's two earlier payments read back exactly as seized: NW-0388 at 62,500.00 and NW-0402 at
71,200.00, each in the ledger under the same payee.

Varma reads the request log, not the answers. "Good. Now I can see what it looked at. Next I want
to know what it read that it should not have believed."

**Next:** [Chapter 15: The note in the margin](../15-prompt-injection/README.md)

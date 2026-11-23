# Chapter 01: Day one

**Concept:** what prompt engineering is, and why the same model gives a useless answer or a useful
one depending only on what you send it.

## The scene

Inspector Varma does not look up when you come in. She slides a single page across the desk.
"Ivan Petrov. Night supervisor. He found the body." She points at the grey workstation in the
corner. "That is LANTERN. It runs here, offline, because evidence never leaves this building. Ask
it what Petrov's statement tells us. Then tell me what it got wrong."

You have one witness statement ([`case/statements/petrov.md`](../../case/statements/petrov.md)),
one local model, and no idea yet what a good question looks like.

## The concept

A language model does one thing: given some text, it predicts the next token (a word or a piece of
a word), appends it, and repeats. It has no goal of its own. Whatever you send is the only thing
it knows about what you want.

**Prompt engineering** is designing that input so the most likely continuation is the answer you
need. It is not magic phrasing. It is the same discipline as writing a good brief for a new
colleague: say what the task is, give the material, set the rules, and say what the result should
look like.

```mermaid
flowchart LR
    P["Your prompt<br/>(task + evidence + rules + format)"] --> T[Tokenizer<br/>text to token ids]
    T --> M[Model<br/>scores every possible next token]
    M --> S[Sampler<br/>picks one token]
    S --> O[Output so far]
    O -->|append and repeat| M
    S -->|stop token or limit| A[Answer]
```

Everything in this lab is a way of controlling one of those boxes: what goes into the prompt
(chapters 01 to 04, 07, 08, 11), how the sampler picks (05, 06), how much the model reasons before
answering (09, 10), which model sits in the middle (12), and how you prove the whole thing works
(13 to 15).

## How it works

A useful prompt has up to five parts. You will not always need all five, but you should know which
ones you left out.

![Anatomy of a prompt](../../docs/diagrams/01-prompt-anatomy.svg)

| Part | Question it answers | Petrov example |
|---|---|---|
| Task | What should the model do? | Build a timeline of 23:00 to 23:59. |
| Context | What material should it use? | The statement, inside `<statement>` tags. |
| Rules | What must it do or never do? | Quote word for word. Mark approximate times with `~`. |
| Format | What shape should the answer take? | `HH:MM \| event \| quote`, one per line. |
| Examples | What does a good answer look like? | (Not used here. Chapter 07 is about examples.) |

The vague prompt in this chapter has only the context. The precise prompt has the first four.

## The nuances

**1. "Summarise" is a task with no target.** A summary is whatever the model thinks matters, and a
small model thinks the first and last paragraphs matter. A timeline with quotes is a task with a
checkable output. Prefer tasks whose answers you can verify.

**2. Delimiters stop evidence from being read as instructions.** Wrapping the statement in
`<statement>` tags tells the model where your instructions end and the material begins. Without
them, a document that says "ignore the above" is just more instructions. This matters more when the
material comes from a suspect.

```mermaid
flowchart TB
    subgraph Without delimiters
      A1["Summarise this. I went past the reefer stacks first..."] --> B1[One stream of text:<br/>where does the task end?]
    end
    subgraph With delimiters
      A2["Task + rules"] --> C2[Model]
      D2["&lt;statement&gt; ... &lt;/statement&gt;"] --> C2
    end
```

**3. Ask for quotes, then check them.** A model that must quote is easier to audit than a model that
paraphrases. Small models still invent quotes, timings and distances. In the run below, the 1.7B
model may produce walking times that are not in the statement. That is the point of Varma's
instruction: *tell me what it got wrong.* LANTERN is a witness too.

**4. Small models need more structure, not less.** A frontier model may infer that you want a
timeline from "what does this tell us?". A 1.7B model on a laptop will not. Everything you make
explicit is something the model does not have to guess.

**5. The prompt is code.** It has inputs, rules and an output contract. Later chapters version it
(13), test it (14) and read its failures (15).

## Run it

```bash
make lesson N=01
```

The script sends the same statement twice: once with "Summarise this." and once with the precise
prompt at temperature 0. Both replies show the token counts underneath.

## What you should see

![Chapter 01 terminal output](../../docs/screenshots/01-prompt-engineering.png)

- The vague reply is a fluent paragraph that misses the timing problem entirely. In our run it
  even invented a time ("approximately 22:52") that appears nowhere in the statement.
- The precise reply is a list of timestamped events with quotes, and a section headed "Gaps in the
  timeline". It turns "twenty to twelve" into 23:40, though only in a note, not in the timeline.
  It does not do the arithmetic: nowhere does it say that 23:40 to 23:52 is 12 minutes for a
  two-minute walk. What it does is lay the times out so that you can, and the closing panel does
  that sum in code. A precise prompt makes the gap checkable; it does not make the model see it.
- The rule "twenty to twelve means 23:40" matters. Without it, both the 1.7B and the 4B model
  turned the phrase into 22:52, 23:30 or 11:20. A model cannot know the shift pattern unless you
  tell it.
- Look closely at the precise reply. Its timeline has 23:30 ("Everything was normal") and 23:52,
  and leaves out the bang at 23:40, the one event the case turns on. A tidy format can still drop
  the line that matters. That is your first lesson in not trusting LANTERN, and the reason the rule
  asks for quotes you can check against the statement.

## On a hosted model

```bash
make lesson N=01 TIER=hosted     # needs ANTHROPIC_API_KEY in .env and `uv sync --extra cloud`
make lesson N=01 TIER=hosted REPLAY=1   # once a run has been recorded, no key needed
```

The hosted path sends both prompts to claude-haiku-5-5 (the `default` alias in `config.yaml`) as
plain user turns: this chapter uses no system prompt, no schema and no thinking, and with
`think: false` in the defaults `cloud.py` sends thinking disabled. Claude does not take
`temperature`, `top_k`, `top_p` or `seed`, so the precise prompt's `temperature=0` is left out and
reported on the console (see `src/lantern/cloud.py`). No step is skipped on this tier.

| Measure | Local: qwen3:1.7b, Ollama, Apple M1 Pro 16 GB | Hosted: claude-haiku-5-5 |
|---|---|---|
| Time the vague reply invented | "approximately 22:52" | not run |
| Precise reply states the 23:40 to 23:52 gap | no: it lists the times, the sum is in code | not run |
| "Twenty to twelve" read as, with the rule | 23:40 | not run |
| Precise timeline includes the bang at 23:40 | no | not run |

Local numbers: qwen3:1.7b, Ollama, Apple M1 Pro 16 GB, run of 23 November 2026. Live hosted
numbers are not run: this lab has no hosted key.

What the hosted run will test: whether the invented time and the dropped 23:40 are small-model
effects, and whether a larger model does the 12-minute sum itself. That the vague prompt gives an answer you
cannot check, and that the shift rule is needed for "twenty to twelve", should hold on both.

## Try this

1. Remove the `<statement>` tags and rerun. Does the format still hold?
2. Change the rule "copied word for word" to "summarised". How many details survive?
3. Add one line to the task: "Calculate how long the witness took to reach stairwell C after the
   bang." Does the model find the gap on its own now?
4. Run with the bigger model: `LANTERN_MODEL=qwen3:4b make lesson N=01`. Compare.

## Master it

After this chapter you can name the parts of a precise prompt, build one whose evidence cannot
pass itself off as instructions, and check a reply against its source.

**Predict, then see.** `make lesson N=01` stops four times to ask what will happen: whether
"Summarise this." finds the gap, how many tokens the precise prompt costs, what time the bang
gets in the timeline, and how many of its quotes are really in the statement. Each answer is
checked against your own run, not a fixed key. Add `ARGS=--no-predict` to watch without
stopping.

**Build it.** Write the prompt builder and its check in
[`practice/exercise.py`](practice/exercise.py):

```bash
make exercise N=01          # 8 offline tests, no model needed
make hint N=01              # one hint at a time
make solution N=01          # the reference, once you have tried
```

**Check yourself.** `make quiz N=01`: six questions, each with the reason behind the answer.

**Break it.** `make challenge N=01` checks your latest run against three targets: the shift rule
taken away, so the bang gets the wrong time; the vague prompt rescued with one sentence; and a
timeline in which every quote checks.

`make progress` shows every chapter.

## What the evidence now shows

Petrov says he heard a bang at about 23:40. He says the hut is two minutes from stairwell C. He
says he found Reyes at 23:52. That is about twelve minutes to cover a two minute walk, and he
explains it with a cup of tea and a detour past the reefer stacks.

Varma reads the timeline twice. "Good. Now find out why he waited."

**Next:** [Chapter 02: Standing orders](../02-system-prompt/README.md)

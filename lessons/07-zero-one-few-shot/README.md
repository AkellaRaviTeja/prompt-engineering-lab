# Chapter 07: Forty-eight messages

**Concept:** zero-shot, one-shot and few-shot prompting. What examples teach a model, what they
teach it by accident, and how to measure whether they helped.

## The scene

Digital forensics has pulled the messages from Reyes's work phone, 1 to 14 March. Forty-eight of
them. Okafor has already sorted them by hand into three piles: threat, logistics, personal. Varma
does not want his piles. She wants to know whether LANTERN can sort the next phone on its own,
because there will be a next phone. "Show me how often it agrees with Daniel," she says. "And show
me where it doesn't."

The messages are in [`case/messages.jsonl`](../../case/messages.jsonl), each with Okafor's label.
Those labels are the **gold standard** you will score against.

## The concept

The number in "N-shot" is the number of worked examples in the prompt.

| Style | What the prompt contains | When it fits |
|---|---|---|
| **Zero-shot** | The task and the label definitions. No examples. | The task is common and the labels are self-explanatory. |
| **One-shot** | The task plus one worked example. | You need to show the output format, or one tricky convention. |
| **Few-shot** | The task plus several examples (typically 2 to 8). | The labels follow house rules the model cannot guess. |

An example is not an instruction. It is evidence of a pattern, and the model continues patterns.
That makes examples powerful and also dangerous: the model learns everything the examples have in
common, including things you did not mean to teach.

```mermaid
flowchart LR
    subgraph Zero-shot
      Z1[System: task + labels] --> Z2[User: message] --> Z3[Assistant: ?]
    end
    subgraph Few-shot as chat turns
      F1[System: task + labels] --> F2[User: example 1] --> F3[Assistant: personal]
      F3 --> F4[User: example 2] --> F5[Assistant: logistics]
      F5 --> F6[...] --> F7[User: message] --> F8[Assistant: ?]
    end
```

## How it works

This lab sends few-shot examples as **earlier turns of the conversation**: each example is a user
message followed by the "correct" assistant reply. Chat models were trained on conversations, so
this is the shape they continue most reliably. Pasting examples as a block of text inside one user
message also works, but small models are more likely to copy the block's layout (answering
`label: threat` or repeating the message) instead of answering.

![Zero, one and few-shot prompt layouts](../../docs/diagrams/07-shots.svg)

The script runs five prompts over the same 36 messages. Twelve messages are used as examples
somewhere, so all twelve are held out of scoring in every mode. That keeps the comparison fair: no
prompt is ever graded on a message it was shown the answer to.

```mermaid
flowchart TB
    D[48 labelled messages] --> E[12 used as examples:<br/>6 clear, 6 boundary]
    D --> S[36 held out for scoring]
    S --> P1[zero-shot, primed]
    S --> P2[zero-shot]
    S --> P3[one-shot]
    S --> P4[few-shot, clear examples]
    S --> P5[few-shot, boundary only]
    P1 & P2 & P3 & P4 & P5 --> A[Accuracy, label counts,<br/>confusion table, disagreements]
```

## The nuances

**1. Measure, do not assume.** Few-shot is often described as "better". On this phone, with this
model, in the captured run, the clear-example few-shot prompt scored 83%, exactly what zero-shot
scored, at three times the tokens per message. (An earlier run had it three points ahead.) The only way to know whether examples help is to score both on held-out data.

**2. The framing is an example too.** The "primed" prompt differs from the plain zero-shot prompt by
one word: "a *murdered* company executive's work phone". That word took the model from 4 threat
labels to 26, and accuracy from 83% to 50%. Everything in the prompt is evidence about what answer
is expected. Keep task descriptions neutral.

**3. Label balance leaks.** If four of your six examples are threats, the model learns that threats
are common. Use roughly the label mix you expect in real data, or an even mix if you do not know.

**4. Order matters, and the last example pulls hardest.** Models weight recent context heavily
(**recency bias**). If all the threat examples come last, borderline messages tilt toward threat.
Interleave labels and end on the least dramatic one.

**5. Examples set the format.** The model copies the shape of the example answers: one word, a
word with a full stop, a sentence. If the examples are sloppy, the output is sloppy. If they answer
in one lowercase word, it will too.

**6. Boundary examples need clear examples around them.** "Boundary only" used six judgement calls
(a colleague's pressure counted as threat, a frightened wife counted as personal, a CEO's probing
question counted as logistics). A large model can learn the rule from those. The 1.7B model learned
"everything is logistics" (0 threats, 29 logistics) and fell to 64%. Teach the clear cases first,
then the edges.

**7. One example can be worse than none.** One-shot with a single threat example (Malhotra's "Can we
talk before you take anything to Elena?") scored 78%, below zero-shot. A single example is a strong
signal about one corner of the space and nothing about the rest.

**8. Gold labels are opinions.** Okafor marked M47, Clarke's "Are you still at the office?", as a
threat. On its own the text is harmless. It is a threat only if you know what happened two hours
later. When the model "gets it wrong", read the message before blaming the model. Some
disagreements are about context the model was never given.

**9. Examples cost tokens on every call.** Six examples took each call from about 105 prompt tokens
to about 320. On a phone with 10,000 messages that is the difference between minutes and hours on a
laptop, and real money on a paid API.

## Run it

```bash
make lesson N=07
make lesson N=07 ARGS=--no-predict   # without stopping for predictions
make lesson N=07 ARGS=--mine   # on your classifier (practice/exercise.py)
```

180 classification calls (5 prompts x 36 messages) at temperature 0. Allow two to six minutes on a
CPU.

## What you should see

![Chapter 07 terminal output](../../docs/screenshots/07-zero-one-few-shot.png)

On our run (qwen3:1.7b, local tier, Apple M1 Pro 16 GB, temperature 0):

| Prompt | Examples | Accuracy | Threat labels (gold: 8) | Tokens per message |
|---|---|---|---|---|
| zero-shot, primed | 0 | 50% | 26 | 106 |
| zero-shot | 0 | 83% | 4 | 105 |
| one-shot | 1 | 78% | 4 | 138 |
| few-shot, clear examples | 6 | 83% | 7 | 319 |
| few-shot, boundary only | 6 | 64% | 0 | 320 |

One-shot also gave one invalid answer. Zero-shot and few-shot with clear examples tied at 83%;
the script reports the first of them, zero-shot, as the best prompt and shows its confusion table.
Every one of its 4 threat labels was right, and it missed the other four threats, all sent to
logistics: three from +88 301, including "The March invoice will be paid on time. Make sure of
it.", "Accidents happen on piers. Especially at night." and "Stairwell C. 23:30.", and Clarke's
M47. It also filed Leo's "can we get pizza friday" and a doctor's message about blood pressure
results as logistics. A model that sorts 83% correctly can still miss the messages that matter
most, which is why the confusion table matters more than the headline number.

## On a hosted model

```bash
make lesson N=07 TIER=hosted              # needs ANTHROPIC_API_KEY in .env, uv sync --extra cloud
make lesson N=07 TIER=hosted ARGS=--mine  # your classifier, with native structured outputs
make lesson N=07 TIER=hosted REPLAY=1     # once a hosted run is recorded (RECORD=1), no key
```

The lesson's own path asks for one word and parses it, on both tiers. Your classifier from the
exercise (`--mine`) sends the label schema as `format=`, which the hosted tier turns into
Claude's native structured outputs (`output_config` with a JSON schema), so every answer is one
of the three labels. Claude takes no `temperature`: the lesson's `temperature=0` is reported and
not sent (see `src/lantern/cloud.py`), so the hosted scores are at the provider's own sampling.

| Measure | Local: qwen3:1.7b | Hosted: claude-haiku-5-5 |
|---|---|---|
| Accuracy: zero-shot, primed | 50% | not run |
| Accuracy: zero-shot | 83% | not run |
| Accuracy: one-shot | 78% | not run |
| Accuracy: few-shot, clear examples | 83% | not run |
| Accuracy: few-shot, boundary only | 64% | not run |
| Threat labels, primed (gold: 8) | 26 | not run |
| Prompt tokens per message, zero-shot / six examples | 105 / 319 | not run |

Local numbers are from the run in "What you should see" (qwen3:1.7b, local tier, Apple M1 Pro 16 GB, temperature 0).

What the hosted run will test: the collapse of "boundary only" to almost all logistics is
expected to be a small-model effect, since a larger model can infer the rule from edge cases;
the pull of the word "murdered" toward threat, and the cost of examples on every call, should
hold on both. M47 should stay a disagreement on any model: the text does not carry the context.

## Try this

1. Swap the order of `EASY` so both threat examples come last. Does the threat count rise?
2. Add `M07` and `M23` to the clear examples (and so to the held-out list). Do the remaining
   +88 301 messages now land as threats?
3. Put the six examples inside the user message as text instead of chat turns. Count the
   `invalid` answers.
4. Run with `LANTERN_MODEL=qwen3:4b make lesson N=07`. Does "boundary only" still collapse?

## Master it

After this chapter you can build zero, one and few-shot prompts with examples as chat turns,
choose and order examples per label, constrain a classifier's answer with a schema, and read a
confusion table instead of trusting one accuracy figure.

**Predict, then see.** `make lesson N=07` stops three times to ask which prompt agrees with
Okafor most, how many threats the primed prompt finds against his count, and how many of his
threats the best prompt misses. Each answer is checked against your own run. Add
`ARGS=--no-predict` to watch without stopping.

**Build it.** Write the few-shot classifier in [`practice/exercise.py`](practice/exercise.py):
a label schema, examples chosen per label and interleaved, examples as turns, and a scorer.

```bash
make exercise N=07             # 8 offline tests, scripted model, no Ollama needed
make hint N=07                 # one hint at a time
make solution N=07             # the reference, once you have tried
make lesson N=07 ARGS=--mine   # all five prompts through your classifier
```

**Check yourself.** `make quiz N=07`: seven questions, each with the reason behind the answer.

**Break it.** `make challenge N=07` checks your latest run against three targets: your
classifier with no invalid answers and at least 80% on clear examples; a reworded task that
finds twice Okafor's threats; and clear examples at 220 tokens a message or fewer without
losing agreement.

`make progress` shows every chapter.

## What the evidence now shows

The threats come from one number, +88 301, the same prefix as Northwind's bank in Port Sabran. They
start on 1 March and end at 15:03 on 14 March with a place and a time: "Stairwell C. 23:30."

Four more messages Okafor filed as threats are not from that number. Two are from Raj Malhotra. Two
are from Simon Clarke.

**Next:** [Chapter 08: Rows for the link chart](../08-structured-output/README.md)

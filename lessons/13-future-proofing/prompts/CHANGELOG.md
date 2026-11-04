# northwind-payments prompt: changelog

Every change to a prompt gets a version, a reason and an eval run, the same as a code change.

## v2 (current)

- Removed `/no_think`. It is a Qwen3 control token, not an instruction. Other model families read
  it as text, and the setting belongs in the request (`think: false`), not the prompt.
- Removed "world's greatest detective", "take a deep breath" and "important for my career".
  They are folklore tuned to older models and they say nothing about the task.
- Replaced "a nice list" with an explicit JSON contract and a schema sent through the API's
  structured output feature.
- Added delimiters around the evidence and a rule for the empty case.
- Eval: `make lesson N=13` runs both versions on two models. v2 must parse on every model.

## v1 (retired)

- First version, written in a hurry against qwen3:1.7b. Gave a usable list once. Never tested
  twice, and its output format was never specified, so the parser was a guess.

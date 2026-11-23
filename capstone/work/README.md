# capstone/work: your folder

This folder is empty on purpose. Everything in it is yours to write: the five modules, the
prompt files, and anything else you need.

Start with the brief, [`../README.md`](../README.md). It lists every file to create and the
contract each function must meet. Then:

1. Create `prompts.py` and `prompts/extract-invoice/v1.yaml`, and run `make capstone`. The
   prompt tests are the first to turn green.
2. Add `pipeline.py`, then `golden.py`, `evaluate.py` and `gate.py`, in that order. Each one
   builds on the one before.
3. When `make capstone` passes, run `make capstone-live` to check your pipeline on the real
   model against the recorded thresholds.

From `lantern` you may import only the model client: `from lantern import chat` (and `Reply`
if you want the type). A test reads your source and fails on anything else.

The reference is in `../solution/`. Read it after you have tried, not before.

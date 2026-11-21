"""Run a lesson on the hosted tier against a fake Anthropic SDK: no key, no network.

    python tests/fake_hosted.py lessons/08-structured-output/run.py [args]

The fake `anthropic` module answers every `messages.create` with a hand-written response in the
SDK's shape: JSON that satisfies the request's schema when it sends `output_config`, a short
refusal ("Not in evidence.") otherwise. It is not a recording of a live call and its answers are
not meant to be right. What it proves is that the chapter's hosted path runs end to end: every
request the chapter makes is built by the native adapter and accepted by its checks, and the
chapter survives an answer it did not expect. Every request is appended as JSON to the file in
FAKE_HOSTED_LOG, if set, so a test can inspect what would have been sent.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
import types
from types import SimpleNamespace as NS


def instance(schema: dict, defs: dict | None = None):
    """A minimal value that satisfies a (strict) JSON schema."""
    defs = defs or schema.get("$defs", {})
    if "$ref" in schema:
        return instance(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return instance(schema["anyOf"][0], defs)
    t = schema.get("type")
    if isinstance(t, list):
        t = t[0]
    if t == "object":
        return {k: instance(v, defs) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [instance(schema["items"], defs)] if schema.get("minItems") else []
    return {"string": "unknown", "number": 0.0, "integer": 0, "boolean": False,
            "null": None}.get(t, None)


class _Err(Exception):
    def __init__(self, *a, **k):
        super().__init__(*a)
        self.response = None
        self.status_code = 500


class Messages:
    def create(self, **kw):
        log = os.getenv("FAKE_HOSTED_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(kw, default=str) + "\n")
        fmt = kw.get("output_config", {}).get("format")
        text = json.dumps(instance(fmt["schema"])) if fmt else "Not in evidence."
        return NS(id="msg_fake", content=[NS(type="text", text=text)],
                  usage=NS(input_tokens=50, output_tokens=5, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0),
                  stop_reason="end_turn")


class Anthropic:
    def __init__(self, **kw):
        self.messages = Messages()


fake = types.ModuleType("anthropic")
fake.Anthropic = Anthropic
for name in ("RateLimitError", "InternalServerError", "APITimeoutError", "APIConnectionError",
             "APIStatusError"):
    setattr(fake, name, type(name, (_Err,), {}))
sys.modules["anthropic"] = fake

os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")
os.environ["LANTERN_TIER"] = "hosted"
os.environ["LANTERN_HOSTED_PROVIDER"] = "anthropic"
os.environ.pop("LANTERN_RECORD", None)
os.environ.pop("LANTERN_REPLAY", None)

if __name__ == "__main__":
    script = sys.argv[1]
    sys.argv = [script, "--no-predict", *sys.argv[2:]]
    runpy.run_path(script, run_name="__main__")

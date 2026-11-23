"""Latency, retries, timeouts, the call log and traces.

Regression tests for the review of 21 November 2026: llm.py reported `eval_duration` only, so a
call that spent most of its time loading the model or reading a long prompt looked fast.
"""

import json

import httpx
import pytest

from lantern import calllog, chat, llm, retry, trace


class Resp:
    def __init__(self, payload, status=200, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self._payload


OK = {"message": {"content": "ok", "tool_calls": [
          {"function": {"name": "ledger_lookup", "arguments": {"ref": "NW-0419"}}}]},
      "prompt_eval_count": 900, "eval_count": 20, "done_reason": "stop",
      "total_duration": 9_000_000_000, "load_duration": 5_000_000_000,
      "prompt_eval_duration": 3_000_000_000, "eval_duration": 1_000_000_000}


@pytest.fixture
def log(tmp_path, monkeypatch):
    p = tmp_path / "calls.jsonl"
    monkeypatch.setenv("LANTERN_CALL_LOG", str(p))
    return p


def test_latency_includes_load_and_prompt_processing(monkeypatch, log):
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: Resp(OK))
    r = chat("x")
    assert r.load_seconds == 5 and r.prompt_seconds == 3 and r.eval_seconds == 1
    assert r.tokens_per_second == pytest.approx(20.0), "generation speed uses eval time"
    # seconds is the measured wall clock of the whole call, not eval_duration
    assert r.seconds < 1, "a fake call returns at once, so the wall clock must be small"
    assert r.tool_calls[0].name == "ledger_lookup"


def test_every_call_is_logged_with_version_model_tokens_and_cost(monkeypatch, log):
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: Resp(OK))
    chat("x", system="Cite evidence.", prompt_version="rules@v3")
    chat("y", system="Cite evidence.")
    chat("y", system="Cite everything.")
    rows = calllog.read(log)
    assert len(rows) == 3
    assert rows[0]["lantern.prompt.version"] == "rules@v3"
    assert rows[0]["gen_ai.request.model"] and rows[0]["gen_ai.usage.input_tokens"] == 900
    assert rows[0]["lantern.cost_usd"] == 0.0
    v1, v2 = rows[1]["lantern.prompt.version"], rows[2]["lantern.prompt.version"]
    assert v1.startswith("auto:") and v1 != v2, "a changed system prompt is a new version"


def test_rate_limits_and_server_errors_are_retried(monkeypatch, log):
    answers = [Resp({}, 429), Resp({}, 503), Resp(OK)]
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: answers.pop(0))
    monkeypatch.setattr(retry.time, "sleep", lambda s: None)
    r = chat("x")
    assert r.attempts == 3 and r.text == "ok"


def test_timeout_is_passed_and_retried_then_gives_up(monkeypatch, log):
    seen = []

    def slow(url, json, timeout):
        seen.append(timeout)
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", slow)
    monkeypatch.setattr(retry.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit, match="gave up after 3 attempts"):
        chat("x", timeout=12, retries=2)
    assert seen == [12, 12, 12]


def test_a_bad_request_is_not_retried():
    calls = []

    def bad():
        calls.append(1)
        raise ValueError("schema rejected")

    with pytest.raises(ValueError):
        retry.call(bad, retries=5, sleep=lambda s: None)
    assert len(calls) == 1


def test_backoff_is_exponential_capped_and_jittered():
    waits = [retry.backoff(n, base=1, cap=10, rng=lambda: 1.0) for n in range(6)]
    assert waits == [1, 2, 4, 8, 10, 10]
    assert retry.backoff(3, base=1, cap=10, rng=lambda: 0.25) == 2.0


def test_retry_after_is_a_floor_on_the_wait():
    slept = []
    script = [retry.Transient("429", retry_after=7.0)]

    def fn():
        if script:
            raise script.pop()
        return "done"

    out, attempts = retry.call(fn, sleep=slept.append, rng=lambda: 0.0)
    assert out == "done" and attempts == 2 and slept == [7.0]


def test_chat_spans_carry_genai_attributes_and_nest(monkeypatch, tmp_path, log):
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: Resp(OK))
    out = tmp_path / "traces.jsonl"
    monkeypatch.setattr(trace, "_tracer", None)
    monkeypatch.setattr(trace, "PATH", out)
    monkeypatch.setenv("LANTERN_TRACE", "1")
    with trace.span("extract invoices", **{"lantern.step": "extract"}):
        chat("x", temperature=0)
    spans = [json.loads(line) for line in out.read_text().splitlines()]
    chat_span = next(s for s in spans if s["name"].startswith("chat "))
    parent = next(s for s in spans if s["name"] == "extract invoices")
    a = chat_span["attributes"]
    assert a["gen_ai.operation.name"] == "chat" and a["gen_ai.usage.input_tokens"] == 900
    assert chat_span["parent_id"] == parent["context"]["span_id"]
    monkeypatch.setattr(trace, "_tracer", None)


def test_a_looping_generation_is_an_empty_answer_not_a_retry(monkeypatch, log):
    """Ollama's "token repeat limit" 500 is the model looping: the same seed loops again."""
    calls = []

    def looping(url, json, timeout):
        calls.append(1)
        return Resp({}, 500, '{"error":"prediction aborted, token repeat limit reached"}')

    monkeypatch.setattr(httpx, "post", looping)
    r = chat("x", seed=3)
    assert len(calls) == 1, "a deterministic loop must not be retried"
    assert r.text == "" and r.stop_reason.startswith("aborted")
    assert calllog.read(log)[0]["gen_ai.response.finish_reasons"] == [r.stop_reason]


def test_backoff_waits_are_kept_out_of_the_latency(monkeypatch, log):
    """Regression (review of 23 Nov 2026): `seconds` included the backoff sleeps."""
    answers = [Resp({}, 503), Resp({}, 503), Resp(OK)]
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: answers.pop(0))
    clock = [0.0]
    monkeypatch.setattr(retry.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    monkeypatch.setattr(retry, "backoff", lambda attempt, base, cap, rng=None: 4.0)
    r = chat("x")
    assert r.attempts == 3, "two server errors then a success is three attempts"
    assert r.wait_seconds == pytest.approx(8.0), "both 4 s waits are counted as waiting"
    assert r.seconds < 1, "the model time of fake calls must not include the 8 s of waiting"
    assert calllog.read(log)[0]["lantern.wait_s"] == 8.0, "the call log keeps the wait apart"


GEN = {"response": " 227,700.00 ", "prompt_eval_count": 812, "eval_count": 9,
       "done_reason": "stop", "eval_duration": 1_000_000_000}


def test_generate_raw_is_retried_logged_and_returns_a_reply(monkeypatch, log):
    """Regression (review of 23 Nov 2026): chapter 04 called /api/generate with no retry or log."""
    seen = []

    def post(url, json, timeout):
        seen.append((url, json, timeout))
        return Resp({}, 503) if len(seen) == 1 else Resp(GEN)

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(retry.time, "sleep", lambda s: None)
    r = llm.generate_raw("<|im_start|>user\nhi<|im_end|>\n", temperature=0, num_predict=300)
    assert seen[0][0].endswith("/api/generate"), "the raw text goes to /api/generate"
    body = seen[0][1]
    assert body["raw"] is True and body["options"]["num_predict"] == 300, "options are passed"
    assert seen[0][2] == 300, "the configured timeout is used, not a fixed 600 s"
    assert r.attempts == 2 and r.text == "227,700.00", "a 503 is retried and the text stripped"
    assert r.prompt_tokens == 812, "prompt tokens come from prompt_eval_count"
    assert calllog.read(log)[0]["gen_ai.usage.input_tokens"] == 812, "the call is logged"


def test_generate_raw_refuses_the_hosted_tier(monkeypatch):
    """A hosted API takes messages only, so there is nothing raw to send."""
    from lantern import config

    monkeypatch.setitem(config.load_config(), "tier", "hosted")
    with pytest.raises(SystemExit, match="only Ollama"):
        llm.generate_raw("x")

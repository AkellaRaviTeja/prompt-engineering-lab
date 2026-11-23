"""The hosted tier's adapters: native features, reported settings, usage and cost.

Regression tests for the review of 21 November 2026: cloud.py used to turn structured output
into a "Reply with JSON only" instruction and silently drop `think`, `seed` and `logprobs`.

The responses here are hand-written in each SDK's documented shape (SimpleNamespace objects
with the same attribute names). They are fixtures, not recordings of a live call.
"""

from types import SimpleNamespace as NS

import httpx
import pytest

from lantern import cloud, llm, retry
from lantern.config import load_config

SCHEMA = {
    "title": "Invoice",
    "type": "object",
    "properties": {
        "invoice_id": {"type": "string", "title": "Invoice Id"},
        "invoice_date": {"type": "string", "format": "date"},
        "vat_number": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
    },
    "required": ["invoice_id", "invoice_date"],
}
TOOLS = [
    {
        "name": "ledger_lookup",
        "description": "Find a ledger row",
        "parameters": {
            "type": "object",
            "properties": {"ref": {"type": "string"}},
            "required": ["ref"],
        },
    }
]


def settings(**over):
    s = {
        "temperature": 0,
        "top_k": 1,
        "top_p": 0.9,
        "seed": 7,
        "num_ctx": 8192,
        "max_tokens": 300,
        "think": False,
        "logprobs": 0,
        "explicit": set(),
        "cache": False,
    }
    s.update(over)
    return s


MSGS = [{"role": "system", "content": "Cite evidence."}, {"role": "user", "content": "NW-0419?"}]


def test_strict_schema_closes_every_object_and_requires_every_field():
    s = cloud.strict_schema(SCHEMA)
    assert s["additionalProperties"] is False
    assert s["required"] == ["invoice_id", "invoice_date", "vat_number"]
    assert "title" not in s and "format" not in s["properties"]["invoice_date"]
    assert SCHEMA["required"] == ["invoice_id", "invoice_date"], "the input must not be mutated"


def test_anthropic_uses_native_structured_output_not_a_prompt():
    kw, _ = cloud.anthropic_request(MSGS, "claude-haiku-5-5", settings(), SCHEMA, None)
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert kw["system"] == "Cite evidence.", "the system prompt must not gain a JSON instruction"
    assert "JSON" not in kw["system"]


def test_anthropic_reports_what_claude_cannot_take():
    kw, unsupported = cloud.anthropic_request(
        MSGS, "claude-haiku-5-5", settings(logprobs=5), None, None
    )
    for name in ("seed", "logprobs", "temperature", "top_k"):
        assert name in unsupported, f"{name} must be reported, not silently dropped"
        assert name not in kw


def test_anthropic_maps_think_to_native_thinking():
    on, _ = cloud.anthropic_request(MSGS, "claude-haiku-5-5", settings(think=True), None, None)
    off, _ = cloud.anthropic_request(MSGS, "claude-haiku-5-5", settings(), None, None)
    sonnet, _ = cloud.anthropic_request(MSGS, "claude-sonnet-5-5", settings(), None, None)
    _, opus = cloud.anthropic_request(MSGS, "claude-opus-5-5", settings(), None, None)
    assert on["thinking"]["type"] == "adaptive"
    assert off["thinking"] == {"type": "disabled"}
    assert sonnet["thinking"] == {"type": "between_tools"}
    assert "think=False" in opus, "a model that cannot turn thinking off must say so"


def test_anthropic_tools_cache_and_tool_turns():
    turns = MSGS + [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "tu_1",
                    "function": {"name": "ledger_lookup", "arguments": {"ref": "NW-0419"}},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tu_1", "content": '{"amount": 9400.0}'},
    ]
    kw, _ = cloud.anthropic_request(turns, "claude-haiku-5-5", settings(cache=True), None, TOOLS)
    assert kw["tools"][0]["input_schema"]["required"] == ["ref"]
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["messages"][1]["content"][0]["type"] == "tool_use"
    assert kw["messages"][2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "content": '{"amount": 9400.0}',
    }


def anthropic_response():
    return NS(
        id="msg_fixture",
        content=[
            NS(type="thinking", thinking="check the ledger"),
            NS(type="text", text=" Not in evidence. "),
            NS(type="tool_use", id="tu_2", name="ledger_lookup", input={"ref": "NW-0402"}),
        ],
        usage=NS(
            input_tokens=40,
            output_tokens=12,
            cache_read_input_tokens=1000,
            cache_creation_input_tokens=0,
        ),
        stop_reason="tool_use",
    )


def test_anthropic_reply_counts_cached_tokens_and_cost():
    r = cloud.anthropic_reply(anthropic_response(), "claude-haiku-5-5", ["seed"])
    assert r.text == "Not in evidence." and r.thinking == "check the ledger"
    assert r.tool_calls[0].name == "ledger_lookup" and r.tool_calls[0].id == "tu_2"
    assert r.prompt_tokens == 1040 and r.cached_tokens == 1000
    r.provider = "anthropic"
    # 40 uncached at 0.10, 1000 cached at 0.01, 12 out at 0.50, per million
    assert llm.cost_of(r) == pytest.approx((40 * 0.10 + 1000 * 0.01 + 12 * 0.50) / 1e6)


def test_long_haiku_prompt_is_billed_at_the_higher_price():
    r = llm.Reply(
        "", "claude-haiku-5-5", prompt_tokens=150_000, output_tokens=0, provider="anthropic"
    )
    assert llm.cost_of(r) == pytest.approx(150_000 * 0.50 / 1e6)


def test_unpriced_model_costs_unknown_not_zero():
    r = llm.Reply("", "gpt-5-mini", prompt_tokens=10, provider="openai")
    assert llm.cost_of(r) is None
    assert llm.cost_of(llm.Reply("", "qwen3:1.7b", prompt_tokens=10)) == 0.0


def test_openai_native_schema_seed_and_reported_settings():
    kw, unsupported = cloud.openai_request(MSGS, "gpt-5-mini", settings(logprobs=3), SCHEMA, TOOLS)
    assert kw["response_format"]["type"] == "json_schema"
    assert kw["response_format"]["json_schema"]["strict"] is True
    sup = load_config()["hosted"]["openai"]["supports"]
    assert ("seed" in kw) == bool(sup["seed"])
    assert "top_k" in unsupported
    assert ("logprobs" in unsupported) == (not sup["logprobs"])
    assert kw["tools"][0]["function"]["name"] == "ledger_lookup"
    assert kw["messages"][0] == {"role": "system", "content": "Cite evidence."}


def test_openai_reply_reads_cached_tokens_and_tool_calls():
    resp = NS(
        choices=[
            NS(
                message=NS(
                    content="ok",
                    tool_calls=[
                        NS(
                            id="c1",
                            function=NS(name="ledger_lookup", arguments='{"ref": "NW-0388"}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
                logprobs=None,
            )
        ],
        usage=NS(
            prompt_tokens=2048, completion_tokens=5, prompt_tokens_details=NS(cached_tokens=1024)
        ),
    )
    r = cloud.openai_reply(resp, "gpt-5-mini", [])
    assert r.cached_tokens == 1024 and r.tool_calls[0].arguments == {"ref": "NW-0388"}


def test_gemini_native_schema_seed_logprobs_and_thinking():
    kw, unsupported = cloud.gemini_request(
        MSGS, "gemini-2.5-flash", settings(think=True, logprobs=2), SCHEMA, TOOLS
    )
    c = kw["config"]
    assert c["response_mime_type"] == "application/json"
    assert c["response_json_schema"] == SCHEMA
    assert c["seed"] == 7 and c["response_logprobs"] is True and c["logprobs"] == 2
    assert c["thinking_config"]["include_thoughts"] is True
    assert c["system_instruction"] == "Cite evidence."
    assert unsupported == []


def test_hosted_tier_resolves_local_names_to_hosted_models(monkeypatch):
    from lantern import config

    cfg = config.load_config()
    monkeypatch.setitem(cfg, "tier", "hosted")
    assert config.provider_of() == "anthropic"
    assert config.model_name(None) == "claude-haiku-5-5"
    assert config.model_name("qwen3:4b") == cfg["hosted"]["anthropic"]["models"]["large"]
    monkeypatch.setitem(cfg, "tier", "cloudy")
    with pytest.raises(SystemExit):
        config.provider_of()


@pytest.mark.parametrize("error", [
    httpx.ReadTimeout("slow"), httpx.ConnectError("refused"), httpx.RemoteProtocolError("drop"),
])
def test_gemini_timeouts_and_dropped_connections_are_retried(monkeypatch, error):
    """Regression (review of 23 Nov 2026): Gemini failed at once on a timeout or a dropped link."""
    from google import genai

    calls = []

    class Models:
        def generate_content(self, **kw):
            calls.append(kw)
            raise error

    class Client:
        def __init__(self, **kw):
            self.models = Models()

    monkeypatch.setattr(genai, "Client", Client)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with pytest.raises(retry.Transient, match="Gemini"):
        cloud._gemini(MSGS, "gemini-2.5-flash", settings(), None, None, timeout=5)
    assert len(calls) == 1, "one attempt per call; lantern.retry decides whether to send again"
    attempts_seen = []

    def flaky():
        attempts_seen.append(1)
        if len(attempts_seen) < 3:
            return cloud._gemini(MSGS, "gemini-2.5-flash", settings(), None, None, timeout=5)
        return "answered"

    out, attempts = retry.call(flaky, retries=3, sleep=lambda s: None)
    assert (out, attempts) == ("answered", 3), "the shared retry loop sends it again"

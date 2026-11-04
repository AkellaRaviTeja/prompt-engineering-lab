import httpx
import pytest

from lantern import case, chat, config, load_config


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"], seen["body"] = url, json
        return FakeResponse({
            "message": {"content": " Paris ", "thinking": "hmm"},
            "prompt_eval_count": 12, "eval_count": 3, "eval_duration": 1_500_000_000,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    return seen


def test_config_has_three_models():
    assert set(load_config()["models"]) == {"default", "small", "large"}


def test_alias_resolves_to_model_name():
    assert config.model_name("small") == load_config()["models"]["small"]
    assert config.model_name("some:other") == "some:other"


def test_chat_sends_system_first_and_config_defaults(captured):
    r = chat("Where?", system="Be brief.")
    body = captured["body"]
    assert captured["url"].endswith("/api/chat")
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    gen = load_config()["generation"]
    assert body["options"]["temperature"] == gen["temperature"]
    assert body["options"]["num_ctx"] == gen["num_ctx"]
    assert body["think"] is gen["think"]
    assert r.text == "Paris" and r.thinking == "hmm"
    assert r.tokens_per_second == pytest.approx(2.0)


def test_chat_overrides_and_format(captured):
    chat("x", temperature=0, top_k=1, seed=42, format={"type": "object"}, logprobs=5)
    body = captured["body"]
    assert body["options"]["temperature"] == 0 and body["options"]["top_k"] == 1
    assert body["options"]["seed"] == 42
    assert body["format"] == {"type": "object"}
    assert body["logprobs"] is True and body["top_logprobs"] == 5


def test_case_files_load():
    assert "Northwind" in case.read("00-briefing.md")
    assert len(case.jsonl("messages.jsonl")) == 48
    assert any(r["reference"] == "NW-0419" for r in case.rows("ledger.csv"))
    assert len(case.files("invoices")) == 8


@pytest.mark.live
def test_live_chat_answers():
    r = chat("Reply with the single word: ready", temperature=0, max_tokens=20)
    assert r.text and r.output_tokens > 0

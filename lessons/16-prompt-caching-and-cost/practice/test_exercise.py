"""Chapter 16: pricing a run and finding cache breakers. First docstring lines are the checklist."""

import pytest

PRICES = {
    "haiku": {
        "input": 0.10, "cache_write": 0.125, "cache_read": 0.01, "output": 0.50,
        "over": {"tokens": 100_000, "input": 0.50, "cache_write": 0.625, "cache_read": 0.05,
                 "output": 2.50},
    },
    "plain": {"input": 2.00, "output": 10.00},
    "unchecked": {"input": None},
}


def rec(model="haiku", inp=0, out=0, read=0, write=0):
    return {"gen_ai.request.model": model, "gen_ai.usage.input_tokens": inp,
            "gen_ai.usage.output_tokens": out, "gen_ai.usage.cache_read.input_tokens": read,
            "gen_ai.usage.cache_creation.input_tokens": write}


def test_plain_input_and_output_are_priced_per_million(impl):
    """Input and output tokens are priced per million at the input and output prices."""
    out = impl.run_cost([rec(inp=2_000, out=1_000)], PRICES)
    assert out["usd"] == pytest.approx((2_000 * 0.10 + 1_000 * 0.50) / 1e6), out
    assert out["calls"] == 1 and out["unpriced"] == []


def test_cache_reads_and_writes_have_their_own_prices(impl):
    """Reads and writes are taken out of the input and priced at cache_read and cache_write."""
    out = impl.run_cost([rec(inp=10_000, read=6_000, write=3_000, out=10)], PRICES)
    want = (1_000 * 0.10 + 6_000 * 0.01 + 3_000 * 0.125 + 10 * 0.50) / 1e6
    assert out["usd"] == pytest.approx(want), f"expected {want}, got {out['usd']}"


def test_missing_cache_prices_fall_back_to_input(impl):
    """A model with no cache prices bills cached tokens at the input price."""
    out = impl.run_cost([rec("plain", inp=1_000, read=800, out=0)], PRICES)
    assert out["usd"] == pytest.approx(1_000 * 2.00 / 1e6), out


def test_a_long_prompt_is_billed_entirely_at_the_higher_tier(impl):
    """Above over['tokens'], every token of that request uses the over prices."""
    under = impl.run_cost([rec(inp=100_000, out=100)], PRICES)["usd"]
    over = impl.run_cost([rec(inp=100_001, out=100)], PRICES)["usd"]
    assert under == pytest.approx((100_000 * 0.10 + 100 * 0.50) / 1e6)
    assert over == pytest.approx((100_001 * 0.50 + 100 * 2.50) / 1e6), (
        "the whole request moves to the higher prices, not just the tokens past the line"
    )


def test_unpriced_models_are_reported_not_free(impl):
    """A model with no checked price is listed once in unpriced and not counted."""
    recs = [rec("unchecked", inp=500), rec("mystery", inp=5), rec("unchecked", inp=1),
            rec(inp=1_000)]
    out = impl.run_cost(recs, PRICES)
    assert out["unpriced"] == ["unchecked", "mystery"], out
    assert out["calls"] == 1 and out["usd"] == pytest.approx(1_000 * 0.10 / 1e6)


def test_finds_a_timestamp_and_a_request_id_in_the_fixed_part(impl):
    """A timestamp or request id before the last user turn is reported with where it is."""
    msgs = [{"role": "system", "content": "Request ID 7f3c. Sent 2026-11-21 09:14:07. Rules..."},
            {"role": "user", "content": "Classify: tugs at 23:10"}]
    found = impl.cache_breakers(msgs)
    assert any(f.startswith("message 0: timestamp '2026-11-21 09:14") for f in found), found
    assert any(f.startswith("message 0: request id") for f in found), found


def test_the_input_turn_is_allowed_to_change(impl):
    """Volatile text in the last user turn is not a breaker: that is the input."""
    msgs = [{"role": "system", "content": "Sort messages into three labels."},
            {"role": "user", "content": "Sent 2026-03-14 23:30:00, id 1b4e28ba-2fa1-11d2-883f"
                                        "-0016d3cca427"}]
    assert impl.cache_breakers(msgs) == [], "only the fixed part can break the cache"


def test_reordered_tools_are_found_against_the_previous_request(impl):
    """Same tools in another order than the previous request is a breaker."""
    a = {"name": "lookup_sender"}
    b = {"name": "lookup_case"}
    msgs = [{"role": "system", "content": "Rules."}, {"role": "user", "content": "x"}]
    found = impl.cache_breakers(msgs, tools=[b, a], previous={"messages": msgs, "tools": [a, b]})
    assert "tools: same tools in a different order" in found, found
    assert impl.cache_breakers(msgs, tools=[a, b],
                               previous={"messages": msgs, "tools": [a, b]}) == []


def test_first_changed_fixed_message_is_reported(impl):
    """Against the previous request, the first fixed message that changed is named."""
    before = [{"role": "system", "content": "Rules v1."}, {"role": "user", "content": "a"}]
    now = [{"role": "system", "content": "Rules v2."}, {"role": "user", "content": "b"}]
    found = impl.cache_breakers(now, previous={"messages": before})
    assert found == ["message 0: differs from the previous request"], found

"""Chapter 14: the tool loop. Each test's first docstring line is what `make exercise` shows."""

from lantern.testing import Scripted, say

SCHEMA = {
    "type": "object",
    "properties": {"reference": {"type": "string", "pattern": r"^[A-Z]{2,3}-\d{4}$"}},
    "required": ["reference"],
    "additionalProperties": False,
}
TOOLS = [{"name": "ledger_lookup", "description": "One ledger row.", "parameters": SCHEMA}]
LEDGER = {"NW-0388": {"payee": "Northwind Freight Ltd", "amount_kbd": "62500.00"}}


def ledger_lookup(reference):
    if reference not in LEDGER:
        raise LookupError(f"no ledger row with reference {reference}")
    return LEDGER[reference]


def go(impl, model, **kw):
    kw.setdefault("functions", {"ledger_lookup": ledger_lookup})
    return impl.run_tools("What is NW-0388?", chat=model, tools=TOOLS, **kw)


def test_validate_names_each_problem(impl):
    """validate() returns [] for good arguments and one message per problem otherwise."""
    assert impl.validate({"reference": "NW-0388"}, SCHEMA) == [], "good arguments must pass"
    assert len(impl.validate({}, SCHEMA)) == 1, "a missing required argument is one problem"
    assert len(impl.validate({"reference": "NW-0388", "x": 1}, SCHEMA)) == 1, (
        "an argument outside properties is a problem when additionalProperties is false")
    assert len(impl.validate({"reference": 388}, SCHEMA)) == 1, "388 is not a string"
    assert len(impl.validate({"reference": "nw 388"}, SCHEMA)) == 1, "the pattern must match"
    assert impl.validate("NW-0388", SCHEMA), "arguments that are not an object are invalid"
    assert impl.validate({"n": True}, {"properties": {"n": {"type": "number"}}}), (
        "true is a boolean, not a number")


def test_answer_without_tools_ends_the_loop(impl):
    """A reply with no tool calls is the answer: one turn, stopped 'answered'."""
    model = Scripted([say("Not in evidence.")])
    out = go(impl, model, system="You are LANTERN.")
    first = model.requests[0]
    assert [m["role"] for m in first["messages"]] == ["system", "user"], (
        "start with the system prompt, then the question")
    assert first.get("tools") == TOOLS, "send the tools with every request"
    assert out["answer"] == "Not in evidence." and out["turns"] == 1
    assert out["stopped"] == "answered" and out["calls"] == []


def test_result_goes_back_with_the_call_id(impl):
    """A valid call runs, and its result goes back as a tool turn with the call's id."""
    model = Scripted([say(calls=[("ledger_lookup", {"reference": "NW-0388"})]), say("62,500.00")])
    out = go(impl, model)
    second = model.requests[1]["messages"]
    assistant, tool = second[-2], second[-1]
    assert assistant["role"] == "assistant" and assistant["tool_calls"], (
        "append the model's request as an assistant turn with tool_calls, before the result")
    call_id = assistant["tool_calls"][0]["id"]
    assert call_id, "every call needs an id, even when the model gave none"
    assert tool["role"] == "tool" and tool["tool_call_id"] == call_id, (
        "the tool turn must carry the id of the call it answers")
    assert "Northwind" in tool["content"]
    assert out["calls"] == [{"name": "ledger_lookup", "arguments": {"reference": "NW-0388"},
                             "valid": True}]
    assert out["answer"] == "62,500.00" and out["turns"] == 2


def test_invalid_arguments_are_rejected_before_the_tool_runs(impl):
    """Arguments that fail the schema return an error to the model; the function never runs."""
    ran = []

    def spy(**kw):
        ran.append(kw)
        return {}

    model = Scripted([say(calls=[("ledger_lookup", {"reference": "nw 388"})]), say("retrying")])
    out = go(impl, model, functions={"ledger_lookup": spy})
    assert ran == [], "a call that fails validation must not reach the function"
    result = model.last_tool_results()[-1]
    assert isinstance(result, dict) and "error" in result, "send {'error': ...} back"
    assert "pattern" in result["error"] or "match" in result["error"], (
        "say what was wrong, so the model can correct itself")
    assert out["calls"][0]["valid"] is False and out["answer"] == "retrying"


def test_unknown_tool_is_an_error_not_a_crash(impl):
    """A tool that does not exist returns {'error': ...} and the loop goes on."""
    model = Scripted([say(calls=[("wire_money", {"to": "X"})]), say("sorry")])
    out = go(impl, model)
    assert "error" in model.last_tool_results()[-1], "unknown tools get an error result"
    assert out["calls"][0]["valid"] is False and out["answer"] == "sorry"


def test_lookup_error_goes_back_to_the_model(impl):
    """A tool's LookupError becomes an error result the model reads, not an exception."""
    model = Scripted([say(calls=[("ledger_lookup", {"reference": "NW-0500"})]), say("no row")])
    out = go(impl, model)
    result = model.last_tool_results()[-1]
    assert result == {"error": "no ledger row with reference NW-0500"}, (
        "return the tool's own message as {'error': str(e)}")
    assert out["calls"][0]["valid"] is True, "the call was valid; the row just is not there"


def test_parallel_calls_each_get_their_own_result(impl):
    """Two calls in one reply: both run, in order, each result carrying its own call's id."""
    model = Scripted([
        say(calls=[("ledger_lookup", {"reference": "NW-0388"}),
                   ("ledger_lookup", {"reference": "NW-0500"})]),
        say("done"),
    ])
    out = go(impl, model)
    msgs = model.requests[1]["messages"]
    ids = [c["id"] for c in msgs[-3]["tool_calls"]]
    assert len(set(ids)) == 2, "two calls need two different ids"
    assert [m["tool_call_id"] for m in msgs[-2:]] == ids, "results in the same order as calls"
    assert out["parallel"] == 1 and len(out["calls"]) == 2


def test_step_cap_stops_a_model_that_never_answers(impl):
    """A model that keeps calling is cut off at max_steps with no answer."""
    model = Scripted([say(calls=[("ledger_lookup", {"reference": "NW-0388"})])] * 3)
    out = go(impl, model, max_steps=3)
    assert model.calls == 3, f"the model was called {model.calls} times; the cap is 3"
    assert out["answer"] is None and out["stopped"] == "max_steps" and out["turns"] == 3

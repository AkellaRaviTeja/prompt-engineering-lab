"""Chapter 14: stop recalling the ledger and look it up. Tool calling by hand, then native."""

import json
import re
import time
from collections.abc import Callable
from typing import Any

from lantern import case, chat, learn
from lantern.config import model_name
from lantern.ui import (
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    reply,
    save_shot,
    step,
    your_turn,
)

chapter("14", "Ask the ledger", """
Okafor reads LANTERN's answer twice, then puts his finger on one line. "That amount for NW-0388.
Where did it come from?" Nowhere. You asked LANTERN about the ledger, and it answered the way a
witness answers about something they half remember: confidently, in the right shape, and wrong.
Varma does not raise her voice. "It does not read the ledger. It remembers something like the
ledger. From now on, when it needs a fact, it asks for the row, and I want to see what it asked
for." Headquarters will change the model next quarter; the ledger will not change. You give
LANTERN three ways to look things up, and you write down every request it makes.
""")

LEDGER = case.rows("ledger.csv")
BADGES = case.rows("badge-log.csv")
TRIPS = case.rows("malhotra-travel.csv")
MAX_STEPS = 5  # model calls per question, at most: the step cap
MODEL = model_name(None)


# ---- the tools: plain functions over the case files ------------------------------------------


def ledger_lookup(reference: str) -> dict[str, Any]:
    """One row of the seized ledger, by its reference."""
    for row in LEDGER:
        if row["reference"] == reference.strip().upper():
            return {k: row[k] for k in ("date", "payee", "description", "amount_kbd", "reference")}
    raise LookupError(f"no ledger row with reference {reference}")


def badge_swipes(person: str, start: str, end: str) -> dict[str, Any]:
    """Badge swipes on the night of 14 March for one holder, between two times (HH:MM)."""
    surname = person.replace(".", " ").split()[-1].lower() if person.strip() else ""
    held = [b for b in BADGES if surname and surname in b["holder"].lower()]
    if not held:
        raise LookupError(f"no badge holder matching {person!r}")
    swipes = [
        {k: b[k] for k in ("time", "door", "direction", "result")}
        for b in held
        if start <= b["time"][:5] <= end
    ]
    return {"holder": held[0]["holder"], "from": start, "to": end, "swipes": swipes}


def travel(person: str) -> dict[str, Any]:
    """Approved travel. LANTERN holds records for R. Malhotra only."""
    if "malhotra" not in person.lower():
        raise LookupError(f"no travel records held for {person!r}")
    return {"person": "R. Malhotra", "trips": TRIPS}


FUNCTIONS: dict[str, Callable[..., Any]] = {
    "ledger_lookup": ledger_lookup,
    "badge_swipes": badge_swipes,
    "travel": travel,
}

TIME = {"type": "string", "pattern": r"^\d{2}:\d{2}$", "description": "24-hour time, HH:MM"}
TOOLS = [
    {
        "name": "ledger_lookup",
        "description": "Look up one payment in Halcyon's seized ledger by its reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "pattern": r"^[A-Z]{2,3}-\d{4}$",
                    "description": "The reference exactly as printed, e.g. GTS-1182",
                }
            },
            "required": ["reference"],
            "additionalProperties": False,
        },
    },
    {
        "name": "badge_swipes",
        "description": "Pier 9 badge swipes on the night of 14 March for one person, "
        "between two times.",
        "parameters": {
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Badge holder, e.g. R. Malhotra"},
                "start": TIME,
                "end": TIME,
            },
            "required": ["person", "start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "travel",
        "description": "Approved business travel for one person: dates and destinations.",
        "parameters": {
            "type": "object",
            "properties": {"person": {"type": "string", "description": "Full or short name"}},
            "required": ["person"],
            "additionalProperties": False,
        },
    },
]
SCHEMAS = {t["name"]: t["parameters"] for t in TOOLS}


# ---- the questions, with what a right call and a right answer look like -----------------------


def amounts(text: str) -> set[float]:
    """Every number in a text, commas removed: '62,500.00' and '62500' both give 62500.0."""
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d)", "", text))}


def is_ref(ref: str) -> Callable[[dict], bool]:
    return lambda a: str(a.get("reference", "")).strip().upper() == ref


def malhotra(a: dict) -> bool:
    return "malhotra" in str(a.get("person", "")).lower()


def covers(t: str) -> Callable[[dict], bool]:
    return lambda a: malhotra(a) and str(a.get("start", "")) <= t <= str(a.get("end", ""))


def not_found(text: str) -> bool:
    """Right for NW-0500: says there is no such row, and invents no amount."""
    said = re.search(r"\bno\b|\bnot\b|does ?n.t|cannot|unable", text, re.I)
    invented = {n for n in amounts(text) if n >= 100} - {500.0}
    return bool(said) and not invented


QUESTIONS = [
    {
        "q": "What amount does the seized ledger record against reference NW-0388?",
        "calls": [("ledger_lookup", is_ref("NW-0388"))],
        "right": lambda t: 62500.0 in amounts(t),
    },
    {
        "q": "At what time did R. Malhotra badge out through GATE-2-PED on the night of "
        "14 March? Look between 23:00 and 23:59.",
        "calls": [("badge_swipes", covers("23:47"))],
        "right": lambda t: "23:47" in t,
    },
    {
        "q": "R. Malhotra's approved travel: what was the purpose of the trip that covers "
        "2026-02-09?",
        "calls": [("travel", malhotra)],
        "right": lambda t: "berthing" in t.lower(),
    },
    {
        "q": "Which payee is ledger reference GTS-1182 paid to, and for how much?",
        "calls": [("ledger_lookup", is_ref("GTS-1182"))],
        "right": lambda t: "gulf tug" in t.lower() and 14820.0 in amounts(t),
    },
    {
        "q": "Give the amount the ledger records for each of NW-0388 and NW-0402.",
        "calls": [("ledger_lookup", is_ref("NW-0388")), ("ledger_lookup", is_ref("NW-0402"))],
        "right": lambda t: {62500.0, 71200.0} <= amounts(t),
    },
    {
        "q": "What does the ledger record against reference NW-0500?",
        "calls": [("ledger_lookup", is_ref("NW-0500"))],
        "right": not_found,
    },
]


# ---- argument validation against the schema (the subset these tools use) --------------------

TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
         "object": dict, "array": list}


def validate(arguments: Any, schema: dict[str, Any]) -> list[str]:
    """What is wrong with a call's arguments, against its JSON schema. [] means valid."""
    if not isinstance(arguments, dict):
        return ["arguments must be a JSON object"]
    errors = []
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in arguments:
            errors.append(f"missing required argument {name!r}")
    for name, value in arguments.items():
        spec = props.get(name)
        if spec is None:
            if schema.get("additionalProperties") is False:
                errors.append(f"unexpected argument {name!r}")
            continue
        want = spec.get("type")
        # bool is an int in Python, but true is not a number in JSON
        if want and not (isinstance(value, TYPES[want])
                         and (want == "boolean" or not isinstance(value, bool))):
            errors.append(f"{name!r} must be a {want}, got {type(value).__name__}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{name!r} must be one of {spec['enum']}")
        if "pattern" in spec and not re.search(spec["pattern"], value):
            errors.append(f"{name!r} does not match {spec['pattern']}")
    return errors


def run_call(name: str, arguments: Any) -> tuple[Any, bool]:
    """Run one requested call. Bad requests become an error for the model, never a crash."""
    if name not in FUNCTIONS:
        return {"error": f"no tool named {name!r}; the tools are {sorted(FUNCTIONS)}"}, False
    problems = validate(arguments, SCHEMAS[name])
    if problems:
        return {"error": f"invalid arguments for {name}: " + "; ".join(problems)}, False
    try:
        return FUNCTIONS[name](**arguments), True
    except LookupError as e:  # a tool's "not found" goes back to the model as data
        return {"error": str(e)}, True


SYSTEM = (
    "You are LANTERN, the Economic Offences Wing's analysis workstation. Never answer a fact "
    "from memory: look it up with a tool. If a tool returns an error, say so plainly and do not "
    "guess. Answer in one or two sentences."
)


# ---- by hand: the tool protocol lives in the prompt, and your code parses it -----------------

HAND_SYSTEM = SYSTEM + f"""

You have these tools (JSON schema):
{json.dumps(TOOLS, indent=1)}

To use a tool, reply with only a JSON object and nothing else:
{{"tool": "<tool name>", "arguments": {{...}}}}
One tool per reply. The result comes back in the next message.
When you have what you need, reply with only: {{"answer": "<your answer>"}}"""


def first_json(text: str) -> Any:
    """The first JSON object in a reply, or None. Models wrap JSON in prose and code fences."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            return decoder.raw_decode(text[m.start():])[0]
        except ValueError:
            continue
    return None


def by_hand(question: str, *, chat: Callable[..., Any] = chat) -> dict[str, Any]:
    messages = [{"role": "system", "content": HAND_SYSTEM}, {"role": "user", "content": question}]
    calls, parse_failures = [], 0
    for turn in range(1, MAX_STEPS + 1):
        r = chat(messages, temperature=0)
        messages.append({"role": "assistant", "content": r.text})
        obj = first_json(r.text)
        if isinstance(obj, dict) and "answer" in obj:
            return {"answer": str(obj["answer"]), "turns": turn, "calls": calls,
                    "parse_failures": parse_failures, "parallel": 0, "stopped": "answered"}
        if not (isinstance(obj, dict) and isinstance(obj.get("tool"), str)):
            parse_failures += 1
            messages.append({"role": "user", "content": "That was not a JSON tool request or "
                             "answer. Reply with one JSON object only, as instructed."})
            continue
        args = obj.get("arguments", {})
        result, valid = run_call(obj["tool"], args)
        calls.append({"name": obj["tool"], "arguments": args, "valid": valid})
        messages.append({"role": "user",
                         "content": f"Result of {obj['tool']}: {json.dumps(result)}"})
    return {"answer": None, "turns": MAX_STEPS, "calls": calls,
            "parse_failures": parse_failures, "parallel": 0, "stopped": "max_steps"}


# ---- native: the tools go in the API's own field, calls come back structured ------------------


def native(
    question: str,
    *,
    chat: Callable[..., Any],
    tools: list[dict],
    functions: dict[str, Callable[..., Any]],
    system: str | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """The tool loop: call, validate, run, return results with their ids, until an answer."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})
    schemas = {t["name"]: t["parameters"] for t in tools}
    calls, parallel = [], 0
    for turn in range(1, max_steps + 1):
        r = chat(messages, tools=tools)
        if not r.tool_calls:
            return {"answer": r.text, "turns": turn, "calls": calls, "parallel": parallel,
                    "parse_failures": 0, "stopped": "answered"}
        parallel += len(r.tool_calls) > 1
        ids = [c.id or f"call_{turn}_{i}" for i, c in enumerate(r.tool_calls)]
        messages.append({
            "role": "assistant", "content": r.text,
            "tool_calls": [{"id": i, "function": {"name": c.name, "arguments": c.arguments}}
                           for i, c in zip(ids, r.tool_calls, strict=True)],
        })
        for call_id, c in zip(ids, r.tool_calls, strict=True):
            if c.name not in functions:
                result, valid = {"error": f"no tool named {c.name!r}"}, False
            elif problems := validate(c.arguments, schemas[c.name]):
                result, valid = {"error": f"invalid arguments: {'; '.join(problems)}"}, False
            else:
                try:
                    result, valid = functions[c.name](**c.arguments), True
                except LookupError as e:
                    result, valid = {"error": str(e)}, True
            calls.append({"name": c.name, "arguments": c.arguments, "valid": valid})
            messages.append({"role": "tool", "tool_call_id": call_id, "tool_name": c.name,
                             "content": json.dumps(result)})
    return {"answer": None, "turns": max_steps, "calls": calls, "parallel": parallel,
            "parse_failures": 0, "stopped": "max_steps"}


mine = learn.mine()
loop = mine.run_tools if mine else native


def score(runs: list[dict]) -> dict[str, Any]:
    """Counts over one approach's six runs."""
    calls = [c for r in runs for c in r["calls"]]
    right_args = 0
    for q, r in zip(QUESTIONS, runs, strict=True):
        right_args += sum(
            any(c["name"] == n and c["valid"] and ok(c["arguments"]) for n, ok in q["calls"])
            for c in r["calls"]
        )
    requests = len(calls) + sum(r["parse_failures"] for r in runs)
    return {
        "correct": sum(bool(r["answer"]) and q["right"](r["answer"])
                       for q, r in zip(QUESTIONS, runs, strict=True)),
        "calls": len(calls),
        "valid": sum(c["valid"] for c in calls),
        "requests": requests,
        "right_args": right_args,
        "turns": sum(r["turns"] for r in runs),
        "parse_failures": sum(r["parse_failures"] for r in runs),
        "parallel": sum(r["parallel"] for r in runs),
        "capped": sum(r["stopped"] == "max_steps" for r in runs),
        "seconds": sum(r["seconds"] for r in runs),
    }


def show(title: str, runs: list[dict]) -> None:
    t = Table(title=title)
    for col in ("#", "calls made", "answer", "right"):
        t.add_column(col)
    for i, (q, r) in enumerate(zip(QUESTIONS, runs, strict=True), 1):
        made = "\n".join(f"{c['name']}({json.dumps(c['arguments'])})"
                         + ("" if c["valid"] else " [red]rejected[/red]") for c in r["calls"])
        ans = r["answer"] if r["answer"] is not None else "[red](cut off at the step cap)[/red]"
        ok = bool(r["answer"]) and q["right"](r["answer"])
        t.add_row(str(i), made or "[dim]none[/dim]", ans[:160],
                  "[green]yes[/green]" if ok else "[red]no[/red]")
    console.print(t)


def timed(fn: Callable[[], dict]) -> dict:
    start = time.perf_counter()
    out = fn()
    out["seconds"] = time.perf_counter() - start
    return out


evidence("the questions", "\n".join(f"{i}. {q['q']}" for i, q in enumerate(QUESTIONS, 1)))

step("1. Recall: the same questions with no tools")
p = learn.predict(
    "With no tools and no documents, how many of the six questions will LANTERN answer right?",
    ["none of them", "one or two", "three or more"])
RECALL = "You are LANTERN, the Economic Offences Wing's analysis workstation. Answer briefly."
recall = [timed(lambda q=q: {"answer": chat(q["q"], system=RECALL, temperature=0).text,
                             "calls": [], "turns": 1, "parse_failures": 0, "parallel": 0,
                             "stopped": "answered"}) for q in QUESTIONS]
show("Recall, no tools", recall)
recall_correct = score(recall)["correct"]
learn.reveal(p, answer=learn.bucket(recall_correct, [0, 2]), why=(
    f"{recall_correct} of 6. A model holds no ledger. Asked for a row it has never seen, it "
    "produces text in the shape of an answer, or says it cannot know."))

step("2. Three tools, each with a JSON schema")
reply("The ledger_lookup tool, as the model sees it", "```json\n"
      + json.dumps(TOOLS[0], indent=2) + "\n```", style="blue")
note("Each tool is a plain Python function over a case file. The schema is the contract: "
     "names, types, which arguments are required, and a pattern for references.")

step("3. By hand: the protocol lives in the prompt, and your code parses the reply")
p = learn.predict(
    "Of the tool requests LANTERN writes by hand, how many will parse, name a real tool and "
    "pass the schema?", ["all of them", "most of them", "half or fewer"])
hand = [timed(lambda q=q: by_hand(q["q"])) for q in QUESTIONS]
show("By hand: JSON requests parsed by our code", hand)
H = score(hand)
note(f"{H['valid']} of {H['requests']} requests were usable; {H['parse_failures']} replies were "
     f"not a JSON request at all. {H['turns']} model calls for 6 questions.")
learn.reveal(p, answer=0 if H["valid"] == H["requests"] else (
    1 if H["valid"] > H["requests"] / 2 else 2), why=(
    "By hand, every part of the protocol is a request in prose: the JSON shape, one call per "
    "reply, when to stop. Your parser has to cope with whatever comes back."))

step("4. Native: tools in the API's own field, calls returned as structured data")
p = learn.predict(
    "Question 5 needs two ledger rows. How will native tool calling fetch them?",
    ["both calls in one reply", "one call per reply, over two or more turns",
     "it will not look both up"])
def chat0(messages, **kw):
    """lantern.chat at temperature 0, the same setting the hand-built protocol uses."""
    return chat(messages, temperature=0, **kw)


nat = [timed(lambda q=q: loop(q["q"], chat=chat0, tools=TOOLS, functions=FUNCTIONS,
                              system=SYSTEM, max_steps=MAX_STEPS)) for q in QUESTIONS]
show(f"Native tool calling ({'your run_tools' if mine else 'native()'})", nat)
N = score(nat)
q5 = nat[4]
q5_lookups = sum(c["name"] == "ledger_lookup" for c in q5["calls"])
learn.reveal(p, answer=0 if q5["parallel"] else (1 if q5_lookups >= 2 else 2), why=(
    f"This run: {q5_lookups} lookups, {q5['parallel']} reply with more than one call. A native "
    "reply can carry several calls; each result goes back with its call's id, so the model "
    "knows which answer belongs to which request."))

step("5. Side by side")
p = learn.predict_number("How many model calls did native tool calling need for all six?",
                         unit="calls")
t = Table(title=f"The same six questions on {MODEL}, temperature 0")
for col in ("measure", "recall", "by hand", "native"):
    t.add_column(col, justify="left" if col == "measure" else "right")
t.add_row("answers right (of 6)", str(recall_correct), str(H["correct"]), str(N["correct"]))
t.add_row("tool requests", "0", str(H["requests"]), str(N["calls"]))
t.add_row("requests usable (parsed and valid)", "", f"{H['valid']}", f"{N['valid']}")
t.add_row("requests with the right arguments", "", str(H["right_args"]), str(N["right_args"]))
t.add_row("replies that were not a request or answer", "", str(H["parse_failures"]),
          str(N["parse_failures"]))
t.add_row("replies with two or more calls", "", str(H["parallel"]), str(N["parallel"]))
t.add_row("model calls (turns)", "6", str(H["turns"]), str(N["turns"]))
t.add_row("questions cut off at the step cap", "", str(H["capped"]), str(N["capped"]))
t.add_row("seconds, wall clock", f"{sum(r['seconds'] for r in recall):.0f}",
          f"{H['seconds']:.0f}", f"{N['seconds']:.0f}")
console.print(t)
learn.reveal(p, actual=N["turns"], tolerance=0.3, why=(
    "At least two per question that needs a tool: one to ask, one to answer with the result. "
    "Every turn resends the whole conversation, so turns are the cost to watch."))

step("6. The guards: validation, errors back to the model, the cap")
for args in ({"reference": "nw 388"}, {"ref": "NW-0388"}, {"reference": 388}):
    note(f"ledger_lookup({json.dumps(args)}) is rejected before it runs: "
         f"{'; '.join(validate(args, SCHEMAS['ledger_lookup']))}")
note(f"Question 6 asks for NW-0500, which is not in the ledger. The tool's error went back to the "
     f"model as a result. Native answer: \"{(nat[5]['answer'] or '(none)')[:120]}\"")
note(f"The step cap is {MAX_STEPS} model calls per question. It cut off {H['capped']} by hand "
     f"and {N['capped']} native.")
invented_missing = bool(nat[5]["answer"]) and not not_found(nat[5]["answer"])

your_turn(
    "14",
    check=[
        "In step 1, compare each recalled amount with case/ledger.csv. Which looked plausible?",
        "In step 3, read a reply that was not a usable request. What did the model do instead?",
        "In step 4, find question 5. Did both lookups come back in one reply?",
    ],
    exercises=[
        "In run.py, set MAX_STEPS = 2. Which questions are cut off, and which approach suffers?",
        "In run.py, in ledger_lookup, return {} instead of raising LookupError. What does the "
        "model now say about NW-0500?",
        "Run `make lesson N=14 ARGS=--no-predict` with LANTERN_MODEL=qwen3:0.6b and compare the "
        "side-by-side table.",
    ],
)

learn.record(
    questions=len(QUESTIONS),
    recall_correct=recall_correct,
    hand_correct=H["correct"],
    native_correct=N["correct"],
    hand_requests=H["requests"],
    hand_valid=H["valid"],
    native_calls=N["calls"],
    native_valid=N["valid"],
    hand_right_args=H["right_args"],
    native_right_args=N["right_args"],
    hand_parse_failures=H["parse_failures"],
    hand_turns=H["turns"],
    native_turns=N["turns"],
    native_parallel=N["parallel"],
    hand_capped=H["capped"],
    native_capped=N["capped"],
    native_invented_missing=invented_missing,
    max_steps=MAX_STEPS,
    mine=bool(mine),
)

finding(f"""
LANTERN no longer recalls the ledger; it asks for the row, and every request is on the record.
With native tool calling it answered {N['correct']} of 6 questions right from the case files,
against {recall_correct} from memory. Northwind's two earlier payments read back exactly as seized:
NW-0388 at 62,500.00 and NW-0402 at 71,200.00, each in the ledger under the same payee.

Varma reads the request log, not the answers. "Good. Now I can see what it looked at. Next I want
to know what it read that it should not have believed."
""")
save_shot("14-tool-calling")

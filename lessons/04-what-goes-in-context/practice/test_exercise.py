"""Chapter 04: the context assembler. Each test's first docstring line is what `make exercise`
shows."""

import pytest

from lantern import case

RULES = "You are LANTERN. Answer only from the <evidence>. Cite every fact as [file]."
SUMMARY = case.read("00-briefing.md")
DOCS = [(p.name, p.read_text()) for p in case.files("invoices") if p.name.startswith("NW-")]
DOCS.append(("reyes-notes.md", "## Friday 06 February 2026\n\nNorthwind is not a vendor.\n"))
HISTORY = [
    {"role": "user", "content": "Who found Reyes, and when?"},
    {"role": "assistant", "content": "Ivan Petrov found him at 23:52 [petrov.md]."},
    {"role": "user", "content": "Which stairwell?"},
    {"role": "assistant", "content": "Stairwell C [00-briefing.md]."},
]
QUESTION = "How much has Halcyon paid Northwind Freight in total this year?"


def build(impl, budget=100_000, **kw):
    args = {"rules": RULES, "summary": SUMMARY, "documents": DOCS, "history": HISTORY,
            "question": QUESTION, "budget": budget}
    args.update(kw)
    return impl.assemble(**args)


def test_parts_come_in_the_briefing_order(impl):
    """Rules as system, the briefing, its acknowledgement, the history, the question last."""
    msgs = build(impl)["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"] + [
        m["role"] for m in HISTORY] + ["user"], "system, briefing, ack, history, question"
    assert msgs[0]["content"] == RULES and msgs[2]["content"] == "Briefing received."
    assert msgs[3:-1] == HISTORY, "the history goes in unchanged, in order"
    assert msgs[-1] == {"role": "user", "content": QUESTION}, "the question is the last turn"


def test_every_part_is_labelled(impl):
    """The summary and each document sit in their own tags, documents inside <evidence>."""
    brief = build(impl)["messages"][1]["content"]
    assert brief.startswith("<case_summary>\n") and "</case_summary>" in brief
    names = [n for n, _ in DOCS]
    at = [brief.find(f'<file name="{n}">') for n in names]
    assert -1 not in at and at == sorted(at), "one <file name=...> per document, in order"
    assert brief.index("</case_summary>") < brief.index("<evidence>") < at[0]
    assert brief.index("</evidence>") > at[-1] and brief.endswith("Briefing received?")


def test_nothing_is_dropped_when_it_fits(impl):
    """Under budget: nothing dropped, and tokens is the size of every message counted."""
    out = build(impl)
    assert out["dropped"] == []
    assert out["tokens"] == sum(impl.approx_tokens(m["content"]) for m in out["messages"])


def test_old_conversation_goes_first(impl):
    """Over budget: the oldest exchange of history goes before any document."""
    full = build(impl)["tokens"]
    out = build(impl, budget=full - 1)
    assert out["messages"][3:-1] == HISTORY[2:], "drop the oldest question and its answer"
    assert out["dropped"] == ["history: Who found Reyes, and when?"]
    assert all(f'name="{n}"' in out["messages"][1]["content"] for n, _ in DOCS)


def test_then_the_least_important_document(impl):
    """With the history gone and still over budget, documents go from the end of the list."""
    no_history = build(impl, history=[])["tokens"]
    out = build(impl, budget=no_history - 1)
    assert out["dropped"][-1] == "reyes-notes.md", "the last document is the least important"
    brief = out["messages"][1]["content"]
    assert "reyes-notes.md" not in brief and 'name="NW-0388.txt"' in brief
    assert out["tokens"] <= no_history - 1


def test_rules_summary_and_question_are_never_dropped(impl):
    """A budget too small for the essentials raises ValueError instead of dropping them."""
    with pytest.raises(ValueError):
        build(impl, budget=50)
    tiny = build(impl, budget=build(impl, documents=[], history=[])["tokens"])
    assert tiny["messages"][-1]["content"] == QUESTION
    assert "<evidence>" not in tiny["messages"][1]["content"], "no documents, no evidence block"
    assert len(tiny["dropped"]) == 2 + len(DOCS), "two exchanges, then every document"


def test_the_budget_uses_the_count_it_is_given(impl):
    """count= decides the size: a counter of words trims differently from one of characters."""
    def words(text):
        return len(text.split())

    out = build(impl, count=words)
    assert out["tokens"] == sum(words(m["content"]) for m in out["messages"])
    out = build(impl, count=words, budget=out["tokens"] - 1)
    assert out["dropped"] == ["history: Who found Reyes, and when?"]

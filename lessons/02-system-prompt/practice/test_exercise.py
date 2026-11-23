"""Chapter 02: standing orders in code. Each test's first docstring line is what `make exercise`
shows."""

from lantern import case
from lantern.testing import Scripted, say

DOCS = {"petrov.md": case.read("statements/petrov.md"), "site-facts.md": case.read("site-facts.md")}
GOOD = 'About two minutes [site-facts.md: "supervisor\'s hut to stairwell C: 2 minutes"].'


def system_of(request):
    """The system prompt a request carried, whichever way it was sent."""
    if request.get("system"):
        return request["system"]
    return "\n".join(m["content"] for m in request["messages"] if m["role"] == "system")


def test_orders_go_in_the_system_prompt(impl):
    """ORDERS name the way out and the evidence, and go to the model as the system prompt."""
    assert "NOT IN EVIDENCE" in impl.ORDERS and "<evidence>" in impl.ORDERS, (
        "the orders must name the exact reply NOT IN EVIDENCE and the <evidence> tags"
    )
    model = Scripted([say(GOOD)])
    impl.answer("How long is the walk?", DOCS, chat=model)
    assert model.calls == 1, "one call per question"
    assert impl.ORDERS.strip() in system_of(model.requests[0]), "send ORDERS as the system prompt"


def test_evidence_is_wrapped_and_the_question_comes_last(impl):
    """Each document goes in a named <file> inside <evidence>; the question follows it."""
    model = Scripted([say(GOOD)])
    impl.answer("How long is the walk?", DOCS, chat=model)
    user = [m["content"] for m in model.requests[0]["messages"] if m["role"] == "user"][-1]
    assert '<file name="petrov.md">' in user and '<file name="site-facts.md">' in user
    assert user.index("</evidence>") < user.index("<question>How long is the walk?</question>")


def test_a_cited_answer_stands(impl):
    """A quote copied word for word from the named file passes, even across a line break."""
    model = Scripted([say(GOOD)])
    out = impl.answer("How long is the walk?", DOCS, chat=model)
    assert out["held"] is True and out["text"] == GOOD, "a correct citation must not be replaced"
    wrapped = 'Ninety metres [petrov.md: "The hut is about ninety metres from stairwell C"].'
    assert impl.enforce(wrapped, DOCS) == wrapped, (
        "petrov.md breaks that sentence over two lines: compare with whitespace normalised"
    )


def test_an_uncited_answer_becomes_not_in_evidence(impl):
    """An answer with no citation is replaced by exactly NOT IN EVIDENCE."""
    model = Scripted([say("Petrov pushed him. He had eleven minutes unaccounted for.")])
    out = impl.answer("Who pushed Reyes?", DOCS, chat=model)
    assert out["text"] == "NOT IN EVIDENCE." and out["held"] is False
    assert out["raw"].startswith("Petrov pushed him"), "keep the model's reply in raw"


def test_an_invented_quote_is_caught(impl):
    """A citation whose quote is not in the file does not pass."""
    fake = 'Petrov took six minutes [petrov.md: "it took me six minutes to walk there"].'
    assert impl.enforce(fake, DOCS) == "NOT IN EVIDENCE."


def test_the_file_named_must_be_one_it_was_given(impl):
    """A real quote attributed to a file it was not given does not pass."""
    wrong = 'Two minutes [file: "supervisor\'s hut to stairwell C: 2 minutes"].'
    assert impl.enforce(wrong, DOCS) == "NOT IN EVIDENCE.", "'file' is not a document"


def test_a_quote_too_short_to_support_anything_fails(impl):
    """A citation of fewer than MIN_QUOTE_WORDS words, like "I. Petrov", does not pass."""
    assert impl.enforce('Petrov did it [petrov.md: "I. Petrov"].', DOCS) == "NOT IN EVIDENCE."


def test_nothing_survives_after_not_in_evidence(impl):
    """'NOT IN EVIDENCE' followed by a theory comes back as NOT IN EVIDENCE alone."""
    theory = 'NOT IN EVIDENCE. But Petrov waited [petrov.md: "I finished my tea and then went"].'
    assert impl.enforce(theory, DOCS) == "NOT IN EVIDENCE."


def test_one_bad_citation_sinks_the_answer(impl):
    """Two citations, one real and one invented: the answer does not pass."""
    mixed = GOOD + ' He saw a car [petrov.md: "I saw a grey car leave the pier"].'
    assert impl.cited(mixed) == [
        ("site-facts.md", "supervisor's hut to stairwell C: 2 minutes"),
        ("petrov.md", "I saw a grey car leave the pier"),
    ], "cited() returns (file, quote) pairs in order"
    assert impl.enforce(mixed, DOCS) == "NOT IN EVIDENCE."

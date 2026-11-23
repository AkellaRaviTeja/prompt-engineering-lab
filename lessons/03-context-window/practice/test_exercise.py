"""Chapter 03: chunk and map. Each test's first docstring line is what `make exercise` shows."""

import pytest

from lantern import case
from lantern.testing import Scripted, say

NOTES = case.read("reyes-notes.md")
LINE = "Northwind is not a vendor"
Q = "\n\nQuestion: What does Reyes say about Northwind Freight? Say NOT FOUND if nothing."


def reader(prompt, **kw):
    """A fake model that answers from the chunk it is given, the way a careful reader would."""
    return say(f'He wrote: "{LINE}. It has no ships, no staff and no office"' if LINE in prompt
               else "NOT FOUND")


def test_split_keeps_every_entry_and_loses_nothing(impl):
    """The notes split into a header and 37 entries, and join back exactly."""
    entries = impl.split_entries(NOTES)
    assert len(entries) == 38, f"expected the header and 37 entries, got {len(entries)}"
    assert all(e.startswith("## ") for e in entries[1:]), "put '## ' back on every entry"
    assert "\n".join(entries) == NOTES, "joining the entries with a newline must give the notes"


def test_chunks_without_overlap_cover_everything_once(impl):
    """size=10, overlap=0: four chunks, every entry exactly once, in order."""
    entries = impl.split_entries(NOTES)
    chunks = impl.chunk_entries(entries, 10, 0)
    assert len(chunks) == 4, f"38 entries in tens is 4 chunks, got {len(chunks)}"
    assert "\n".join(chunks) == NOTES, "no overlap: the chunks joined are the notes"


def test_overlap_repeats_the_edge_of_the_last_chunk(impl):
    """size=10, overlap=2: each chunk starts with the last two entries of the one before."""
    entries = [f"## e{i}\n" for i in range(20)]
    chunks = impl.chunk_entries(entries, 10, 2)
    assert len(chunks) == 3, f"windows start at 0, 8 and 16: expected 3 chunks, got {len(chunks)}"
    assert chunks[1].startswith("## e8\n") and chunks[2].startswith("## e16\n")
    assert chunks[-1].endswith("## e19\n"), "the last chunk ends with the last entry"


def test_bad_sizes_are_refused(impl):
    """An overlap as big as the window, or a window of zero, raises ValueError."""
    for size, overlap in ((5, 5), (5, 7), (0, 0), (5, -1)):
        with pytest.raises(ValueError):
            impl.chunk_entries(["a", "b", "c"], size, overlap)


def test_one_call_per_chunk_with_the_question_last(impl):
    """Each chunk goes in <notes> tags with the question after it: one call per chunk."""
    model = Scripted([say("NOT FOUND") for _ in range(5)])
    out = impl.read_notes(NOTES, Q, chat=model, size=10, overlap=1)
    assert model.calls == len(out["replies"]) == 5, "38 entries, windows of 10 stepping 9: 5 calls"
    prompt = model.requests[0]["messages"][-1]["content"]
    assert prompt.startswith("<notes>\n") and prompt.endswith("</notes>" + Q)
    assert [r["found"] for r in out["replies"]] == [False] * 5 and out["hits"] == []


def test_the_line_in_the_middle_is_found(impl):
    """With a model that reads its chunk, the line from 6 February comes back as a verified hit."""
    out = impl.read_notes(NOTES, Q, chat=reader, size=10, overlap=1)
    found = [i for i, r in enumerate(out["replies"]) if r["found"]]
    assert found == [2], f"only the chunk holding 6 February should report a find, got {found}"
    assert out["hits"] and all(h["chunk"] == 2 for h in out["hits"])
    assert any(LINE in h["quote"] for h in out["hits"]), "the hit carries Reyes's words"


def test_an_invented_quote_is_not_a_hit(impl):
    """A chunk that claims a quote it does not contain gives no hit."""
    model = Scripted([say('Reyes wrote "Northwind pays Raj in cash every month."')]
                     + [say("NOT FOUND")] * 4)
    out = impl.read_notes(NOTES, Q, chat=model, size=10, overlap=1)
    assert out["replies"][0]["found"] is True, "the reply did not say NOT FOUND"
    assert out["hits"] == [], "that quote is not in the chunk: it must not count"
    assert impl.quotes_in('he said "no staff and no\n office"', "no staff and no office") == [
        "no staff and no\n office"], "compare with whitespace normalised; return the passage"

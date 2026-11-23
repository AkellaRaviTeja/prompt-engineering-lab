"""Chapter 03 exercise: make Reyes's notes fit by reading them in overlapping pieces.

The whole file is too long to be read properly in one prompt. Cut it on entry boundaries into
chunks that overlap, ask the same question of each chunk (the map step), and keep only the hits
whose quotes really are in the chunk they came from.

Fill in the four functions. Grade them with `make exercise N=03` (offline: the tests use a
scripted model). Then run the live lesson on your code: `make lesson N=03 ARGS=--mine`.
Stuck? `make hint N=03`.
"""

from __future__ import annotations

import re  # noqa: F401  (the solution uses it)
from collections.abc import Callable
from typing import Any


def split_entries(notes: str) -> list[str]:
    """The notes as [header, entry, entry, ...]; each entry starts with '## '.

    Every entry in reyes-notes.md begins with a line '## <date>'. Joining the list with "\\n"
    must give back the notes exactly.
    """
    # TODO 1: split on "\n## " and put the "## " back on every entry after the header.
    raise NotImplementedError("TODO 1: split the notes into entries")


def chunk_entries(entries: list[str], size: int, overlap: int = 0) -> list[str]:
    """Windows of `size` entries; each starts `overlap` entries before the last one ended.

    Each chunk is its entries joined with "\\n". The last chunk ends with the last entry, and no
    chunk is added once one has reached the end. Raise ValueError unless size >= 1 and
    0 <= overlap < size (an overlap as big as the window would never move forward).
    """
    # TODO 2: check the arguments.
    # TODO 3: step through the entries by size - overlap, stopping once a chunk reaches the end.
    raise NotImplementedError("TODO 2 and 3: chunk with overlap")


def quotes_in(reply: str, chunk: str) -> list[str]:
    """The quoted passages (three words or more) in a reply that appear in the chunk verbatim.

    A passage is text between straight double quotes or curly ones. Compare with whitespace
    normalised: the notes are hard-wrapped. A quote that is not in the chunk is an invention.
    """
    # TODO 4: find the quoted passages and keep the ones that are really in the chunk.
    raise NotImplementedError("TODO 4: check the quotes")


def read_notes(
    notes: str, question: str, *, chat: Callable[..., Any], size: int, overlap: int = 1
) -> dict[str, Any]:
    """Map the question over overlapping chunks of the notes. Returns {"replies", "hits"}.

    For each chunk, one call:
        chat(f"<notes>\\n{chunk}\\n</notes>{question}", num_ctx=8192, temperature=0,
             max_tokens=150)
    replies  one dict per chunk, in order: {"chunk", "text", "prompt_tokens", "found"}, where
             found is True unless the reply contains NOT FOUND
    hits     {"chunk": index, "quote": passage} for every verified quote in a found reply
    """
    # TODO 5: split, chunk, ask each chunk, and collect replies and verified hits.
    raise NotImplementedError("TODO 5: the map step")

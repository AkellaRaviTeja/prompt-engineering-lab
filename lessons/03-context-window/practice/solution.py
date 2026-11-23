"""Chapter 03 reference solution: chunk with overlap, then map. Compare it with yours."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


def split_entries(notes: str) -> list[str]:
    """The notes as [header, entry, entry, ...]; each entry starts with '## '."""
    parts = notes.split("\n## ")
    return [parts[0]] + ["## " + p for p in parts[1:]]


def chunk_entries(entries: list[str], size: int, overlap: int = 0) -> list[str]:
    """Windows of `size` entries; each starts `overlap` entries before the last one ended."""
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("need size >= 1 and 0 <= overlap < size")
    chunks, start = [], 0
    while True:
        chunks.append("\n".join(entries[start : start + size]))
        if start + size >= len(entries):
            return chunks
        start += size - overlap


def quotes_in(reply: str, chunk: str) -> list[str]:
    """The quoted passages (three words or more) in a reply that appear in the chunk verbatim."""
    flat = " ".join(chunk.split())
    found = re.findall(r'["“]([^"”]+)["”]', reply)
    return [q for q in found if len(q.split()) >= 3 and " ".join(q.split()) in flat]


def read_notes(
    notes: str, question: str, *, chat: Callable[..., Any], size: int, overlap: int = 1
) -> dict[str, Any]:
    """Map the question over overlapping chunks of the notes. Returns {"replies", "hits"}."""
    replies, hits = [], []
    for i, chunk in enumerate(chunk_entries(split_entries(notes), size, overlap)):
        r = chat(f"<notes>\n{chunk}\n</notes>{question}", num_ctx=8192, temperature=0,
                 max_tokens=150)
        found = "NOT FOUND" not in r.text
        replies.append(
            {"chunk": chunk, "text": r.text, "prompt_tokens": r.prompt_tokens, "found": found}
        )
        if found:
            hits += [{"chunk": i, "quote": q} for q in quotes_in(r.text, chunk)]
    return {"replies": replies, "hits": hits}

"""The sampler's arithmetic, in plain Python, so you can see every step.

Ollama runs on llama.cpp, whose default sampler chain is roughly:
    top_k  ->  top_p  ->  min_p  ->  temperature  ->  draw one token at random
These functions reproduce that chain on the log-probabilities Ollama returns.
"""

from __future__ import annotations

import math
import random

# The question and the start of LANTERN's answer. Ending the conversation on an
# assistant turn makes the model continue that sentence (a "prefill"), so the
# very next token is the word we care about.
NORTHWIND_QUESTION = (
    "Northwind Freight Ltd is paid large sums by Halcyon Maritime but has no ships, no staff, "
    "no office, no VAT number and only a PO box abroad. What is Northwind most likely to be?"
)
NORTHWIND_PREFILL = "Northwind is most likely a"


def northwind_messages() -> list[dict[str, str]]:
    return [
        {"role": "user", "content": NORTHWIND_QUESTION},
        {"role": "assistant", "content": NORTHWIND_PREFILL},
    ]


def first_token_distribution(reply) -> list[tuple[str, float]]:
    """(token, logprob) pairs for the first generated token, most likely first."""
    top = reply.logprobs[0]["top_logprobs"]
    return [(t["token"], t["logprob"]) for t in top]


def normalise(weights: list[tuple[str, float]]) -> list[tuple[str, float]]:
    total = sum(w for _, w in weights)
    return [(t, w / total) for t, w in weights]


def with_temperature(dist: list[tuple[str, float]], temperature: float) -> list[tuple[str, float]]:
    """Divide every log-probability by T, then softmax again.

    T < 1 sharpens the distribution (the favourite gets more), T > 1 flattens it.
    T = 0 is a special case: always take the single most likely token (greedy).
    """
    if temperature == 0:
        best = max(dist, key=lambda x: x[1])[0]
        return [(t, 1.0 if t == best else 0.0) for t, _ in dist]
    scaled = [(t, lp / temperature) for t, lp in dist]
    peak = max(s for _, s in scaled)
    return normalise([(t, math.exp(s - peak)) for t, s in scaled])


def top_k(probs: list[tuple[str, float]], k: int) -> list[tuple[str, float]]:
    """Keep only the k most likely tokens, then renormalise."""
    return normalise(sorted(probs, key=lambda x: -x[1])[:k])


def top_p(probs: list[tuple[str, float]], p: float) -> list[tuple[str, float]]:
    """Keep the smallest set of tokens whose probabilities add up to at least p."""
    kept, total = [], 0.0
    for t, w in sorted(probs, key=lambda x: -x[1]):
        kept.append((t, w))
        total += w
        if total >= p:
            break
    return normalise(kept)


def sampler_chain(dist_logprobs, *, temperature: float, k: int, p: float):
    """llama.cpp order: truncate with top_k and top_p, then apply temperature."""
    probs = normalise([(t, math.exp(lp)) for t, lp in dist_logprobs])
    probs = top_p(top_k(probs, k), p)
    return with_temperature([(t, math.log(w)) for t, w in probs], temperature)


def draw(probs: list[tuple[str, float]], rng: random.Random) -> str:
    r, acc = rng.random(), 0.0
    for t, w in probs:
        acc += w
        if r <= acc:
            return t
    return probs[-1][0]

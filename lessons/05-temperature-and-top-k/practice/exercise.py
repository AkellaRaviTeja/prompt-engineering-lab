"""Chapter 05 exercise: write the sampler yourself.

Five small functions that together are the whole sampler: reshape with temperature, cut with
top_k and top_p, chain them in the right order, and draw one token with a seeded random number.
Grade it with `make exercise N=05` (offline, no model). When every test passes, run the lesson
on your sampler: `make lesson N=05 ARGS=--mine`.

Stuck? `make hint N=05`. Start again? `make exercise-reset N=05`.

A distribution is a list of (token, value) pairs. `dist` holds log-probabilities, as Ollama
returns them; `probs` holds probabilities that add up to 1.
"""

from __future__ import annotations

import math  # noqa: F401  (the solution uses it)
import random

Dist = list[tuple[str, float]]


def with_temperature(dist: Dist, temperature: float) -> Dist:
    """(token, log-probability) pairs in; (token, probability) pairs out, reshaped by T.

    Divide every log-probability by T, then softmax: exp of each, divided by their sum.
    T < 1 sharpens, T > 1 flattens. T = 0 is greedy: probability 1.0 for the most likely token
    and 0.0 for every other one. Keep every token, in the order given.
    """
    # TODO 1: T == 0 is greedy. Return 1.0 for the highest log-probability, 0.0 for the rest.
    # TODO 2: divide each log-probability by T. Subtract the largest result before exp(), so a
    #         small T cannot overflow; it does not change the answer.
    # TODO 3: exp() each one and divide by their sum.
    raise NotImplementedError("TODO 1 to 3: temperature")


def top_k(probs: Dist, k: int) -> Dist:
    """The k most likely tokens, most likely first, renormalised to add up to 1."""
    # TODO 4: sort by probability, highest first; keep k; divide each by the kept total.
    raise NotImplementedError("TODO 4: top_k")


def top_p(probs: Dist, p: float) -> Dist:
    """The smallest set of most likely tokens whose probabilities reach p, renormalised.

    The token that takes the running total to p or past it is kept.
    """
    # TODO 5: walk the tokens from most to least likely, adding each, and stop once the running
    #         total is >= p. Renormalise what you kept.
    raise NotImplementedError("TODO 5: top_p")


def sampler_chain(dist: Dist, *, temperature: float, k: int, p: float) -> Dist:
    """llama.cpp's order: cut with top_k, then top_p, on the raw probabilities; then temperature.

    `dist` is (token, log-probability). Returns (token, probability) for the tokens that
    survive, ready for draw().
    """
    # TODO 6: turn the log-probabilities into probabilities (exp, then renormalise).
    # TODO 7: cut with top_k, then top_p. The cut uses the raw probabilities, not the reshaped
    #         ones: temperature comes last.
    # TODO 8: apply temperature to what survived (with_temperature takes log-probabilities, so
    #         pass math.log of each kept probability).
    raise NotImplementedError("TODO 6 to 8: the chain")


def draw(probs: Dist, rng: random.Random) -> str:
    """One token, drawn with the given probabilities, using only `rng` for randomness.

    The same seed must give the same token, and a token with probability 0 is never drawn.
    """
    # TODO 9: take r = rng.random() (one number in [0, 1)). Walk the tokens adding up their
    #         probabilities; return the first token whose running total is past r.
    # TODO 10: rounding can leave the total a hair under 1. If the walk ends, return the last
    #          token with a probability above 0.
    raise NotImplementedError("TODO 9 and 10: the draw")

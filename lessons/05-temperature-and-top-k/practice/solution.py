"""Chapter 05 reference solution: the sampler chain. Compare it with yours after you have tried."""

from __future__ import annotations

import math
import random

Dist = list[tuple[str, float]]


def _normalise(weights: Dist) -> Dist:
    total = sum(w for _, w in weights)
    return [(t, w / total) for t, w in weights]


def with_temperature(dist: Dist, temperature: float) -> Dist:
    """(token, log-probability) pairs in; (token, probability) pairs out, reshaped by T."""
    if temperature == 0:
        best = max(dist, key=lambda x: x[1])[0]
        return [(t, 1.0 if t == best else 0.0) for t, _ in dist]
    scaled = [(t, lp / temperature) for t, lp in dist]
    peak = max(s for _, s in scaled)
    return _normalise([(t, math.exp(s - peak)) for t, s in scaled])


def top_k(probs: Dist, k: int) -> Dist:
    """The k most likely tokens, most likely first, renormalised."""
    return _normalise(sorted(probs, key=lambda x: -x[1])[:k])


def top_p(probs: Dist, p: float) -> Dist:
    """The smallest set of most likely tokens whose probabilities reach p, renormalised."""
    kept, total = [], 0.0
    for t, w in sorted(probs, key=lambda x: -x[1]):
        kept.append((t, w))
        total += w
        if total >= p:
            break
    return _normalise(kept)


def sampler_chain(dist: Dist, *, temperature: float, k: int, p: float) -> Dist:
    """llama.cpp's order: cut with top_k, then top_p, on the raw probabilities; then temperature."""
    probs = _normalise([(t, math.exp(lp)) for t, lp in dist])
    kept = top_p(top_k(probs, k), p)
    return with_temperature([(t, math.log(w)) for t, w in kept], temperature)


def draw(probs: Dist, rng: random.Random) -> str:
    """One token, drawn with the given probabilities, using only `rng` for randomness."""
    r, acc = rng.random(), 0.0
    for t, w in probs:
        acc += w
        if r < acc:
            return t
    return next(t for t, w in reversed(probs) if w > 0)

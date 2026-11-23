"""Chapter 05: the sampler chain. Each test's first docstring line is what `make exercise` shows."""

import math
import random
from collections import Counter

# A next-token distribution as log-probabilities, shaped like the chapter's Northwind one.
DIST = [(" company", math.log(0.40)), (" **", math.log(0.27)), (" fict", math.log(0.10)),
        (" fictional", math.log(0.05)), (":\n\n", math.log(0.04)), (" ______", math.log(0.03)),
        (" courier", math.log(0.01))]


def probs_of(pairs):
    return dict(pairs)


def test_temperature_one_gives_back_the_raw_probabilities(impl):
    """At T = 1 the probabilities are the raw ones, renormalised to add up to 1."""
    out = probs_of(impl.with_temperature(DIST, 1.0))
    total = sum(math.exp(lp) for _, lp in DIST)
    assert abs(sum(out.values()) - 1) < 1e-9, "the probabilities must add up to 1"
    assert abs(out[" company"] - 0.40 / total) < 1e-9, "T = 1 must not reshape anything"


def test_low_temperature_sharpens_and_high_flattens(impl):
    """T below 1 gives the favourite more; T above 1 gives it less, and the tail more."""
    raw = probs_of(impl.with_temperature(DIST, 1.0))
    cold = probs_of(impl.with_temperature(DIST, 0.2))
    hot = probs_of(impl.with_temperature(DIST, 1.5))
    assert cold[" company"] > 0.8 > raw[" company"], "divide the log-probabilities by T"
    assert hot[" company"] < raw[" company"] and hot[" courier"] > raw[" courier"], (
        "a high T should move probability from the favourite into the tail"
    )
    assert [t for t, _ in impl.with_temperature(DIST, 0.2)] == [t for t, _ in DIST], (
        "keep every token, in the order given"
    )


def test_temperature_zero_is_greedy(impl):
    """T = 0 gives the most likely token probability 1 and every other token 0."""
    out = probs_of(impl.with_temperature(DIST, 0))
    assert out[" company"] == 1.0, "T = 0 means always take the most likely token"
    assert all(w == 0.0 for t, w in out.items() if t != " company"), "every other token gets 0"


def test_top_k_keeps_the_k_most_likely(impl):
    """top_k keeps exactly k tokens, most likely first, and renormalises them."""
    probs = [(t, math.exp(lp)) for t, lp in reversed(DIST)]  # deliberately least likely first
    out = impl.top_k(probs, 3)
    assert [t for t, _ in out] == [" company", " **", " fict"], f"kept {out}"
    assert abs(sum(w for _, w in out) - 1) < 1e-9, "renormalise what you keep"


def test_top_p_keeps_the_token_that_crosses_p(impl):
    """top_p keeps the smallest set reaching p, including the token that crosses it."""
    probs = [(t, math.exp(lp)) for t, lp in DIST]
    kept = [t for t, _ in impl.top_p(probs, 0.5)]
    assert kept == [" company", " **"], f"0.40 is short of 0.5, 0.40 + 0.27 reaches it: {kept}"
    peaked = [("714", 0.97), ("7", 0.02), ("2", 0.01)]
    assert [t for t, _ in impl.top_p(peaked, 0.9)] == ["714"], "a sure model keeps one token"


def test_chain_cuts_before_temperature(impl):
    """The chain cuts on the raw probabilities, then applies temperature to what is left."""
    out = probs_of(impl.sampler_chain(DIST, temperature=0.2, k=40, p=0.75))
    kept = {t for t, w in out.items() if w > 0}
    assert kept == {" company", " **", " fict"}, (
        f"kept {sorted(kept)}: top_p must cut the raw distribution (0.40 + 0.27 + 0.10 reaches "
        "0.75); cutting after temperature would keep only ' company'"
    )
    assert out[" company"] > 0.8, "temperature 0.2 must still sharpen what survives"
    assert abs(sum(out.values()) - 1) < 1e-9


def test_chain_applies_top_k_too(impl):
    """top_k in the chain removes tokens even when top_p would keep them."""
    out = impl.sampler_chain(DIST, temperature=1.0, k=2, p=1.0)
    assert {t for t, w in out if w > 0} == {" company", " **"}, f"k=2 should keep two: {out}"


def test_draw_is_seeded_and_follows_the_probabilities(impl):
    """The same seed draws the same tokens, and frequencies follow the probabilities."""
    probs = [("a", 0.7), ("b", 0.2), ("c", 0.1), ("never", 0.0)]
    one = [impl.draw(probs, random.Random(42)) for _ in range(3)]
    assert len(set(one)) == 1, "a fresh Random(42) each time must draw the same token"
    rng = random.Random(7)
    counts = Counter(impl.draw(probs, rng) for _ in range(10_000))
    assert counts["never"] == 0, "a token with probability 0 must never be drawn"
    assert abs(counts["a"] / 10_000 - 0.7) < 0.03 and abs(counts["c"] / 10_000 - 0.1) < 0.02, (
        f"draw frequencies {dict(counts)} do not follow the probabilities"
    )

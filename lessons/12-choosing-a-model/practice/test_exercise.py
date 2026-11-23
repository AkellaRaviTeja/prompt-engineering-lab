"""Chapter 12: the model scorecard. First docstring lines are what `make exercise` lists."""

import pytest


def rows(model, seconds, correct, cost=0.0):
    return [{"model": model, "correct": c, "seconds": s, "cost_usd": cost}
            for s, c in zip(seconds, correct, strict=True)]


def test_percentile_is_nearest_rank(impl):
    """p50 of 1, 2, 3, 4 is 2; p95 of sixteen values is the largest one."""
    assert impl.percentile([4.0, 1.0, 3.0, 2.0], 50) == 2.0, "sort first, then rank ceil(q*n)"
    sixteen = [float(i) for i in range(1, 17)]
    assert impl.percentile(sixteen, 95) == 16.0, "ceil(0.95 * 16) = 16: the slowest call"
    assert impl.percentile([5.0], 95) == 5.0


def test_percentile_of_nothing_is_an_error(impl):
    """An empty list raises ValueError instead of returning a made-up number."""
    with pytest.raises(ValueError):
        impl.percentile([], 50)


def test_one_row_per_model_in_first_seen_order(impl):
    """Rows for small, large, small give two scorecard rows: small then large."""
    data = (rows("small", [0.1], [True]) + rows("large", [0.9], [True])
            + rows("small", [0.2], [False]))
    out = impl.scorecard(data)
    assert [r["model"] for r in out] == ["small", "large"], out
    assert out[0]["n"] == 2 and out[1]["n"] == 1


def test_accuracy_and_latency_percentiles(impl):
    """Accuracy is correct over n; p95 catches the one slow call that p50 hides."""
    secs = [0.3] * 15 + [4.2]  # one call paid for loading the model
    out = impl.scorecard(rows("medium", secs, [True] * 12 + [False] * 4))[0]
    assert out["accuracy"] == 0.75, f"12 of 16 is 0.75, got {out['accuracy']}"
    assert out["p50_s"] == 0.3 and out["p95_s"] == 4.2, out


def test_cost_per_correct_answer(impl):
    """Total cost divided by correct answers, not by questions asked."""
    out = impl.scorecard(rows("haiku", [1.0] * 4, [True, True, False, False], cost=0.001))[0]
    assert out["cost_per_correct"] == pytest.approx(0.002), (
        "4 calls at 0.001 is 0.004, over 2 correct answers"
    )


def test_unknown_price_is_unknown_not_free(impl):
    """One call with no checked price makes the model's cost per correct answer None."""
    data = rows("x", [1.0, 1.0], [True, True], cost=0.001)
    data[1]["cost_usd"] = None
    assert impl.scorecard(data)[0]["cost_per_correct"] is None, "never count an unknown as 0"


def test_no_correct_answers_is_none_not_a_crash(impl):
    """A model that got nothing right has no cost per correct answer, and no ZeroDivisionError."""
    out = impl.scorecard(rows("tiny", [0.1, 0.1], [False, False], cost=0.0))[0]
    assert out["accuracy"] == 0.0 and out["cost_per_correct"] is None, out


def test_no_rows_is_an_error(impl):
    """An empty result list raises ValueError: an empty scorecard proves nothing."""
    with pytest.raises(ValueError):
        impl.scorecard([])

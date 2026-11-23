"""Chapter 06: the reproducibility check. Each test's first docstring line is what `make exercise`
shows."""

import hashlib

import pytest

from lantern.testing import Scripted, say

PLATE = "Which plate matches KB 7?4 ?LR? Reply with the plate only."
FIXED = {"temperature": 0, "seed": 7, "top_k": 40, "top_p": 0.9, "max_tokens": 60}


def test_same_prompt_and_settings_every_run(impl):
    """Every run sends the identical prompt with the identical settings."""
    model = Scripted([say("KB 714 FLR") for _ in range(4)])
    impl.check_reproducible(PLATE, chat=model, runs=4, settings=FIXED)
    assert model.calls == 4, f"asked for 4 runs, the model was called {model.calls} times"
    for req in model.requests:
        assert req["messages"] == [{"role": "user", "content": PLATE}], "send the prompt as is"
        sent = {k: v for k, v in req.items() if k != "messages"}
        assert sent == FIXED, f"every run must use the same settings; one sent {sent}"


def test_identical_answers_are_reproducible(impl):
    """Five identical answers: one distinct answer, agreement 1.0, reproducible."""
    out = impl.check_reproducible(PLATE, chat=Scripted([say("KB 714 FLR")] * 5), runs=5)
    assert out["distinct"] == 1 and out["reproducible"] is True, out
    assert out["agreement"] == 1.0 and out["most_common"] == "KB 714 FLR", out
    assert out["answers"] == ["KB 714 FLR"] * 5, "keep every answer, in order"


def test_one_different_answer_is_not_reproducible(impl):
    """One run in five that differs makes the finding not reproducible."""
    replies = [say("227,700.00"), say("227,700.00"), say("226,700.00"), say("227,700.00"),
               say("227,700.00")]
    out = impl.check_reproducible("total?", chat=Scripted(replies), runs=5)
    assert out["reproducible"] is False, "a single different answer is enough to fail"
    assert out["distinct"] == 2 and out["counts"] == {"227,700.00": 4, "226,700.00": 1}, out
    assert out["most_common"] == "227,700.00" and abs(out["agreement"] - 0.8) < 1e-9, out


def test_whitespace_alone_is_not_a_different_answer(impl):
    """Answers that differ only in surrounding whitespace count as the same answer."""
    replies = [say("KB 714 FLR"), say("KB 714 FLR\n"), say("  KB 714 FLR")]
    out = impl.check_reproducible(PLATE, chat=Scripted(replies), runs=3)
    assert out["distinct"] == 1 and out["reproducible"] is True, (
        f"strip each answer before comparing: got {out['answers']}"
    )


def test_three_answers_from_five_runs(impl):
    """Three different answers are counted as three, and agreement is the largest share."""
    texts = ["a", "b", "a", "c", "a"]
    out = impl.check_reproducible("q", chat=Scripted([say(t) for t in texts]), runs=5)
    assert out["distinct"] == 3 and out["most_common"] == "a", out
    assert abs(out["agreement"] - 0.6) < 1e-9, f"3 of 5 runs gave 'a': {out['agreement']}"


def test_one_run_proves_nothing(impl):
    """runs < 2 raises ValueError, before the model is called."""
    model = Scripted([say("KB 714 FLR")])
    with pytest.raises(ValueError):
        impl.check_reproducible(PLATE, chat=model, runs=1)
    assert model.calls == 0, "refuse before calling the model"


def test_record_names_the_prompt_and_settings(impl):
    """The result carries the settings used and the prompt's SHA-256."""
    out = impl.check_reproducible(PLATE, chat=Scripted([say("x")] * 2), runs=2, settings=FIXED)
    assert out["settings"] == FIXED, "record the settings every run used"
    assert out["prompt_sha256"] == hashlib.sha256(PLATE.encode()).hexdigest(), (
        "hash the prompt text (UTF-8) with hashlib.sha256 and keep the hex digest"
    )

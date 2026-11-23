"""lantern.learn and scripts/learn.py: predictions, targets, and every chapter's practice.yaml."""

import ast
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from lantern import learn

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("learn_cli", ROOT / "scripts" / "learn.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

PRACTICE = sorted((ROOT / "lessons").glob("[0-9][0-9]-*/practice/practice.yaml"))


def test_bucket_upper_bounds():
    assert [learn.bucket(v, [3, 6, 15]) for v in (1, 3, 4, 6, 7, 15, 16)] == [0, 0, 1, 1, 2, 2, 3]


def test_predictions_are_silent_without_a_person(monkeypatch):
    monkeypatch.setattr(learn, "interactive", lambda: False)
    p = learn.predict("q?", ["a", "b"])
    assert not p.asked and learn.reveal(p, answer=1) is None
    n = learn.predict_number("how many?")
    assert learn.reveal(n, actual=10) is None


def test_reveal_scores_a_number_within_tolerance(monkeypatch, tmp_path):
    monkeypatch.setattr(learn, "PROGRESS", tmp_path)
    p = learn.Prediction("tokens?", guess=2500.0, asked=True)
    assert learn.reveal(p, actual=2860, tolerance=0.3) is True
    p = learn.Prediction("tokens?", guess=500.0, asked=True)
    assert learn.reveal(p, actual=2860, tolerance=0.3) is False


def test_targets_are_checked_against_metrics():
    ok, lines = cli.evaluate(
        "turns <= 6 and flows_in_report == 4", {"turns": 5, "flows_in_report": 4}
    )
    assert ok and len(lines) == 2
    ok, _ = cli.evaluate("mine == true and turns < 3", {"mine": True, "turns": 3})
    assert not ok
    ok, _ = cli.evaluate("missing >= 1", {})
    assert not ok
    with pytest.raises(ValueError):
        cli.evaluate("turns is small", {})


def test_there_is_practice_to_check():
    assert PRACTICE, "no lessons/*/practice/practice.yaml found"


@pytest.mark.parametrize("path", PRACTICE, ids=lambda p: p.parent.parent.name)
def test_practice_file_is_complete(path):
    """Every chapter's practice: objectives, a check, an exercise with tests, and challenges."""
    folder = path.parent
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert d["chapter"] == folder.parent.name[:2]
    assert d["title"] and len(d["objectives"]) >= 3
    assert len(d["quiz"]) >= 5, "a chapter check needs at least five questions"
    for q in d["quiz"]:
        assert q["q"] and q["why"], q
        assert all(isinstance(o, str) for o in q["options"]), f"quote options with ': ' in {q['q']}"
        assert 2 <= len(q["options"]) <= 6
        assert q["answer"] in learn.LETTERS[: len(q["options"])], q["q"]
    answers = [q["answer"] for q in d["quiz"]]
    assert len(set(answers)) > 1, "the right answer should not always be the same letter"
    ex = d["exercise"]
    assert ex["title"] and ex["task"] and len(ex["hints"]) >= 2
    for f in ("exercise.py", "solution.py", "test_exercise.py"):
        assert (folder / f).exists(), f"missing practice/{f}"
    stub = (folder / "exercise.py").read_text(encoding="utf-8")
    assert "TODO" in stub and "NotImplementedError" in stub, "the stub must be unfinished"
    tests = (folder / "test_exercise.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^def test_", tests, re.M)) >= 4
    assert len(d["challenges"]) >= 2
    ids = [c["id"] for c in d["challenges"]]
    assert len(ids) == len(set(ids))
    for c in d["challenges"]:
        assert c["title"] and c["goal"] and c["change"]
        cli.evaluate(c["target"], {})  # parses


@pytest.mark.parametrize("path", PRACTICE, ids=lambda p: p.parent.parent.name)
def test_lesson_records_every_metric_its_challenges_use(path):
    """Each challenge target names metrics that run.py passes to learn.record()."""
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    run = (path.parent.parent / "run.py").read_text(encoding="utf-8")
    assert run.count("learn.predict") >= 2, "run.py should ask at least two predictions"
    recorded = recorded_metrics(run)
    assert recorded, "run.py must call learn.record() with keyword metrics"
    for c in d["challenges"]:
        for name in re.findall(r"([a-z_][a-z0-9_]*)\s*(?:<=|>=|==|!=|<|>)", c["target"]):
            assert name in recorded, f"{c['id']}: learn.record() in run.py never records {name}"


def recorded_metrics(source):
    """The keyword names passed to every learn.record(...) call in a lesson's source."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "learn"
        ):
            names |= {k.arg for k in node.keywords if k.arg}
    return names


def test_recorded_metrics_reads_only_record_keywords():
    src = "turns = 3\nlearn.record(flows=4, mine=False)\nother.record(turns=1)\n"
    assert recorded_metrics(src) == {"flows", "mine"}


@pytest.mark.parametrize("path", PRACTICE, ids=lambda p: p.parent.parent.name)
def test_shuffled_options_keep_the_right_answer(path):
    """The check shuffles options; the answer letter must still point at the same option."""
    for q in yaml.safe_load(path.read_text(encoding="utf-8"))["quiz"]:
        s = cli.shuffled(q)
        assert sorted(s["options"]) == sorted(q["options"])
        right = q["options"][learn.LETTERS.index(q["answer"])]
        assert s["options"][learn.LETTERS.index(s["answer"])] == right
        assert cli.shuffled(q) == s, "the order must be the same every time"


@pytest.mark.parametrize("path", PRACTICE, ids=[p.parent.parent.name for p in PRACTICE])
def test_challenge_targets_compare_with_values_or_recorded_metrics(path):
    """A target's right-hand side is a number, a boolean, or a metric run.py records."""
    run_py = (path.parent.parent / "run.py").read_text()
    for c in yaml.safe_load(path.read_text())["challenges"]:
        for part in re.split(r"\s+and\s+", c["target"].strip()):
            m = cli.CONDITION.match(part)
            assert m, f"{c['id']}: cannot read {part!r}"
            raw = m.group(3)
            if cli.METRIC_NAME.fullmatch(raw) and raw not in ("true", "false", "null"):
                assert re.search(rf"\b{raw}\s*=", run_py), (
                    f"{path.parent.parent.name} {c['id']}: {raw!r} is not a recorded metric")
            else:
                assert isinstance(yaml.safe_load(raw), (int, float, bool)), (
                    f"{path.parent.parent.name} {c['id']}: {part!r} is not a value")


def test_a_target_can_compare_two_metrics():
    ok, _ = cli.evaluate("hand_turns <= native_turns", {"hand_turns": 8, "native_turns": 8})
    assert ok
    ok, _ = cli.evaluate("hand_turns <= native_turns", {"hand_turns": 18, "native_turns": 8})
    assert not ok
    ok, _ = cli.evaluate("a <= missing", {"a": 1})
    assert not ok, "a missing metric on the right must not count as met"

"""Every chapter that calls a model runs on the hosted tier, end to end.

Each chapter's run.py runs under tests/fake_hosted.py: the real lesson, the real native adapter,
and a fake Anthropic SDK that answers in the SDK's shape (see that file). A chapter fails here if
its hosted path breaks: an Ollama-only step not guarded, a setting the adapter cannot build, or a
crash on an answer the chapter did not expect.

When a real recorded hosted run exists (recordings/hosted/NN.jsonl), the chapter is also replayed
from it with LANTERN_REPLAY=1, with no key and no network.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = sorted(p for p in (ROOT / "lessons").glob("[0-9][0-9]-*") if (p / "run.py").exists())
# Extra arguments for chapters whose hosted run needs them (18 reruns promptfoo otherwise).
ARGS = {"18": ["--reuse"], "19": []}


def run(lesson: Path, extra_env: dict, log: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "FAKE_HOSTED_LOG": str(log), "LANTERN_CALL_LOG": "",
           "LANTERN_TRACE": "0", "LANTERN_CHAPTER": lesson.name[:2], **extra_env}
    return subprocess.run(
        [sys.executable, str(ROOT / "tests" / "fake_hosted.py"), str(lesson / "run.py"),
         *ARGS.get(lesson.name[:2], [])],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )


@pytest.mark.parametrize("lesson", LESSONS, ids=[p.name for p in LESSONS])
def test_chapter_runs_on_the_hosted_tier(lesson, tmp_path):
    log = tmp_path / "requests.jsonl"
    r = run(lesson, {}, log)
    assert r.returncode == 0, f"{lesson.name} failed on the hosted tier:\n{r.stderr[-3000:]}"
    requests = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    for kw in requests:
        assert "temperature" not in kw and "seed" not in kw, "unsupported settings were sent"
        assert kw["model"].startswith("claude-"), "a local model name reached the hosted API"


@pytest.mark.parametrize("lesson", LESSONS, ids=[p.name for p in LESSONS])
def test_chapter_replays_from_its_recording(lesson, tmp_path):
    rec = ROOT / "recordings" / "hosted" / f"{lesson.name[:2]}.jsonl"
    if not rec.exists():
        pytest.skip(f"no recorded hosted run for chapter {lesson.name[:2]}: not run")
    env = {**os.environ, "LANTERN_TIER": "hosted", "LANTERN_REPLAY": "1",
           "LANTERN_CALL_LOG": "", "LANTERN_TRACE": "0"}
    r = subprocess.run([sys.executable, str(lesson / "run.py"), "--no-predict"], cwd=ROOT,
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]

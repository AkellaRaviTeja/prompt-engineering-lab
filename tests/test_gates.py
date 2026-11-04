import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script)],
                          capture_output=True, text=True)


def test_prose_gate_passes_and_counts():
    r = run("lint_prose.py")
    assert r.returncode == 0, r.stdout
    assert "checked" in r.stdout and "checked 0 files" not in r.stdout


def test_prose_gate_catches_em_dash(tmp_path, monkeypatch):
    bad = ROOT / "lessons" / "_tmp_bad.md"
    bad.write_text("a " + chr(0x2014) + " b\n", encoding="utf-8")
    try:
        r = run("lint_prose.py")
        assert r.returncode == 1 and "em dash" in r.stdout
    finally:
        bad.unlink()


def test_structure_gate_counts_lessons():
    r = run("check_lessons.py")
    assert r.returncode == 0, r.stdout
    assert "checked 0 lessons" not in r.stdout

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


def test_structure_gate_catches_placeholders():
    import importlib.util

    spec = importlib.util.spec_from_file_location("cl", ROOT / "scripts" / "check_lessons.py")
    cl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cl)
    text = "Intro.\n\nSEE\n\n| a | b |\n@@T11@@\nNot run yet. LANTERN said NO. See NUANCE3.\n"
    found = [m.group(0).strip() for m in cl.PLACEHOLDER.finditer(text)]
    assert found == ["SEE", "@@T11@@", "NUANCE3"]

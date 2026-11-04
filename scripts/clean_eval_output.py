"""Replace this machine's absolute repo path in promptfoo output with a relative one.

promptfoo resolves `file://` variables to absolute paths and writes them into
evals/output/results.json. The file is committed so chapter 15 works without a
15 minute eval run, so it must not carry anyone's home directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted((ROOT / "evals" / "output").glob("*.json")) + sorted(
        (ROOT / "evals" / "output").glob("*.txt"))
    changed = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        clean = text.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")
        if clean != text:
            path.write_text(clean, encoding="utf-8")
            changed += 1
    print(f"clean_eval_output: checked {len(files)} files, rewrote {changed}")
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main())

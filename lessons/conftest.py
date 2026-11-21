"""Fixtures for every chapter's practice tests (lessons/NN-*/practice/test_exercise.py).

`impl` is the module under test. `make test` checks the reference `solution.py`, so the tests
and the solutions stay honest; `make exercise N=NN` sets LANTERN_EXERCISE=learner and checks your
`exercise.py` instead.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load(path: Path):
    name = f"practice_{path.parent.parent.name[:2]}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def impl(request):
    folder = Path(request.path).parent
    which = "exercise.py" if os.getenv("LANTERN_EXERCISE") == "learner" else "solution.py"
    return load(folder / which)

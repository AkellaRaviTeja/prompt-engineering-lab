"""Fixtures for the capstone tests: the modules under test, loaded from one folder.

`make capstone-solution` checks capstone/solution/, so the tests and the reference stay honest;
`make capstone` sets LANTERN_CAPSTONE=learner and checks your capstone/work/ instead.

Each fixture imports one module by its plain name (prompts, pipeline, golden, evaluate, gate)
with that folder first on sys.path, so your modules can import each other the same way.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

CAPSTONE = Path(__file__).resolve().parents[1]
ROOT = CAPSTONE.parent
CASE = ROOT / "case"
MODULES = ("prompts", "pipeline", "golden", "evaluate", "gate")


def folder() -> Path:
    return CAPSTONE / ("work" if os.getenv("LANTERN_CAPSTONE") == "learner" else "solution")


def load(name: str):
    where = folder()
    if str(where) != sys.path[0]:
        if str(where) in sys.path:
            sys.path.remove(str(where))
        sys.path.insert(0, str(where))
    for mod in MODULES:  # drop a same-named module loaded from anywhere else
        m = sys.modules.get(mod)
        if m is not None and Path(getattr(m, "__file__", "") or "").parent != where:
            del sys.modules[mod]
    if not (where / f"{name}.py").exists():
        pytest.fail(f"{where.relative_to(ROOT)}/{name}.py does not exist yet")
    return importlib.import_module(name)


@pytest.fixture
def impl_dir() -> Path:
    return folder()


@pytest.fixture
def prompts():
    return load("prompts")


@pytest.fixture
def pipeline():
    return load("pipeline")


@pytest.fixture
def golden():
    return load("golden")


@pytest.fixture
def evaluate():
    return load("evaluate")


@pytest.fixture
def gate():
    return load("gate")

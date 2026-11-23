"""The capstone is built from a blank folder: from lantern it may import only the model client."""

from __future__ import annotations

import ast

ALLOWED = {"chat", "Reply"}


def test_imports_only_the_client(impl_dir):
    """Every .py file imports nothing from lantern but chat (and Reply), and never the solution."""
    files = [p for p in impl_dir.rglob("*.py") if "__pycache__" not in p.parts]
    assert files, f"{impl_dir.name}/ has no Python files yet"
    problems = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
                problems += [f"{path.name}: import {n}" for n in names
                             if n.split(".")[0] == "lantern" or "solution" in n]
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "solution" in mod:
                    problems.append(f"{path.name}: from {mod} import ...")
                elif mod == "lantern":
                    problems += [f"{path.name}: from lantern import {a.name}"
                                 for a in node.names if a.name not in ALLOWED]
                elif mod.startswith("lantern."):
                    problems.append(f"{path.name}: from {mod} import ...")
            elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "import_module":
                problems.append(f"{path.name}: importlib.import_module (import by name instead)")
    assert not problems, "only `from lantern import chat` is allowed: " + "; ".join(problems)

"""Read evidence from the case/ folder."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from lantern.config import ROOT

CASE = ROOT / "case"


def read(name: str) -> str:
    return (CASE / name).read_text(encoding="utf-8")


def rows(name: str) -> list[dict[str, str]]:
    with open(CASE / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def jsonl(name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in read(name).splitlines() if line.strip()]


def files(folder: str) -> list[Path]:
    return sorted((CASE / folder).glob("*"))

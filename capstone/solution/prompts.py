"""Versioned prompts stored as files: prompts/<name>/<version>.yaml.

A prompt file holds everything that decides what the prompt does: the system text, the user
template with {{placeholders}}, the JSON schema the reply must match, and the settings it runs
with. A changed prompt is a new file with a new version, so every logged call names the exact
text that produced it.

    p = load_prompt("extract-invoice", "v1")
    p.id                                  # "extract-invoice@v1"
    p.render(invoice=text)                # [{"role": "system", ...}, {"role": "user", ...}]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent / "prompts"
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    user: str
    schema: dict[str, Any]
    system: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    @property
    def id(self) -> str:
        """The label every call is logged with: name@version."""
        return f"{self.name}@{self.version}"

    def render(self, **fields: Any) -> list[dict[str, str]]:
        """The messages for one input. A placeholder with no value raises KeyError."""

        def fill(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in fields:
                raise KeyError(f"{self.id} needs a value for {{{{{key}}}}}")
            return str(fields[key])

        messages = []
        if self.system.strip():
            messages.append({"role": "system", "content": PLACEHOLDER.sub(fill, self.system)})
        messages.append({"role": "user", "content": PLACEHOLDER.sub(fill, self.user)})
        return messages


def _number(version: str) -> tuple[int, str]:
    digits = re.sub(r"\D", "", version)
    return (int(digits) if digits else 0, version)


def versions(name: str, root: Path | None = None) -> list[str]:
    """Every version of a prompt, oldest first (v2 before v10)."""
    folder = (root or ROOT) / name
    if not folder.is_dir():
        known = sorted(p.name for p in (root or ROOT).glob("*") if p.is_dir())
        raise LookupError(f"no prompt named {name!r}; prompts: {', '.join(known) or 'none'}")
    return sorted((p.stem for p in folder.glob("*.yaml")), key=_number)


def load_prompt(name: str, version: str, root: Path | None = None) -> Prompt:
    """Load one prompt version. Unknown names and versions raise LookupError."""
    have = versions(name, root)
    if version not in have:
        raise LookupError(f"{name} has no version {version!r}; versions: {', '.join(have)}")
    path = (root or ROOT) / name / f"{version}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("name") != name or str(data.get("version")) != version:
        raise ValueError(
            f"{path} says it is {data.get('name')}@{data.get('version')}, "
            f"but it is stored as {name}@{version}"
        )
    for key in ("user", "schema"):
        if not data.get(key):
            raise ValueError(f"{path} has no {key!r}")
    if not isinstance(data["schema"], dict):
        raise ValueError(f"{path}: schema must be a JSON schema object")
    return Prompt(
        name=name,
        version=version,
        user=data["user"],
        schema=data["schema"],
        system=data.get("system") or "",
        settings=dict(data.get("settings") or {}),
        description=data.get("description") or "",
    )

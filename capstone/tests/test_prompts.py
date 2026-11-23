"""Versioned prompts: loaded by name and version from files, rendered, unknown versions refused."""

from __future__ import annotations

import pytest
import yaml

SCHEMA = {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]}


def write(root, name, stored_as, **overrides):
    data = {
        "name": name,
        "version": stored_as,
        "system": "You sort messages for {{unit}}.",
        "user": "Sort this: {{text}}",
        "schema": SCHEMA,
        "settings": {"temperature": 0, "max_tokens": 50},
        **overrides,
    }
    path = root / name / f"{stored_as}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_load_prompt_by_name_and_version(prompts, tmp_path):
    """load_prompt returns the version asked for, with its text, schema, settings and id."""
    write(tmp_path, "sort", "v1", user="old: {{text}}")
    write(tmp_path, "sort", "v2")
    p = prompts.load_prompt("sort", "v2", root=tmp_path)
    assert p.version == "v2", f"asked for v2, got {p.version}"
    assert p.user == "Sort this: {{text}}", f"v2's user template, got {p.user!r}"
    assert p.schema == SCHEMA, "the schema is read from the file unchanged"
    assert p.settings == {"temperature": 0, "max_tokens": 50}, f"settings: {p.settings}"
    assert p.id == "sort@v2", f"the logged id is name@version, got {p.id!r}"


def test_unknown_version_is_refused(prompts, tmp_path):
    """An unknown version raises LookupError that names the versions that exist."""
    write(tmp_path, "sort", "v1")
    with pytest.raises(LookupError) as e:
        prompts.load_prompt("sort", "v9", root=tmp_path)
    assert "v1" in str(e.value), f"the error should list the known versions: {e.value}"


def test_unknown_prompt_is_refused(prompts, tmp_path):
    """An unknown prompt name raises LookupError, not a crash further down."""
    write(tmp_path, "sort", "v1")
    with pytest.raises(LookupError):
        prompts.load_prompt("summarise", "v1", root=tmp_path)


def test_file_must_match_its_path(prompts, tmp_path):
    """A file stored as v2 that says it is v1 inside is refused with ValueError."""
    write(tmp_path, "sort", "v2", version="v1")
    with pytest.raises(ValueError):
        prompts.load_prompt("sort", "v2", root=tmp_path)


def test_versions_sort_by_number(prompts, tmp_path):
    """versions() lists every version oldest first, so v10 comes after v2."""
    for v in ("v10", "v1", "v2"):
        write(tmp_path, "sort", v)
    got = prompts.versions("sort", root=tmp_path)
    assert got == ["v1", "v2", "v10"], f"expected numeric order, got {got}"


def test_render_fills_every_placeholder(prompts, tmp_path):
    """render() returns a system message then a user message, every {{placeholder}} filled."""
    write(tmp_path, "sort", "v1")
    p = prompts.load_prompt("sort", "v1", root=tmp_path)
    msgs = p.render(unit="the EOW", text="Two tugs at 14:00.")
    assert [m["role"] for m in msgs] == ["system", "user"], f"roles: {msgs}"
    assert msgs[0]["content"] == "You sort messages for the EOW.", msgs[0]["content"]
    assert msgs[1]["content"] == "Sort this: Two tugs at 14:00.", msgs[1]["content"]
    with pytest.raises(KeyError):
        p.render(unit="the EOW")


def test_render_without_system_text(prompts, tmp_path):
    """A prompt with no system text renders to the user message alone."""
    write(tmp_path, "sort", "v1", system="")
    msgs = prompts.load_prompt("sort", "v1", root=tmp_path).render(text="hello")
    assert msgs == [{"role": "user", "content": "Sort this: hello"}], f"got {msgs}"


def test_shipped_prompts(prompts):
    """The pipeline ships extract-invoice v1 and classify-message v1 and v2, each with a schema."""
    inv = prompts.load_prompt("extract-invoice", "v1")
    props = inv.schema.get("properties", {})
    for field in ("invoice_id", "vendor", "date", "total"):
        assert field in props, f"extract-invoice@v1 schema has no {field}"
    assert "{{invoice}}" in inv.user + inv.system, "extract-invoice takes {{invoice}}"
    for v in ("v1", "v2"):
        p = prompts.load_prompt("classify-message", v)
        label = p.schema.get("properties", {}).get("label", {})
        assert sorted(label.get("enum", [])) == ["logistics", "personal", "threat"], (
            f"classify-message@{v} must constrain label to the three labels: {label}"
        )
        for key in ("{{sender}}", "{{text}}"):
            assert key in p.user + p.system, f"classify-message@{v} takes {key}"

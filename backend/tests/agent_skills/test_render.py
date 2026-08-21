"""Tests for skill catalog / load-result rendering helpers."""

from __future__ import annotations

from app.agent_skills.render import (
    escape_text,
    format_catalog_entries,
    format_catalog_entry,
    normalize_catalog_description,
    render_skill_content,
    resource_base_from_location,
)
from app.agent_skills.types import AgentSkillManifest


def test_normalize_catalog_description_collapses_whitespace_no_truncate() -> None:
    long = "a" * 600
    assert normalize_catalog_description(f"  hello\n\tworld  {long}") == (
        f"hello world {long}"
    )


def test_escape_text() -> None:
    assert escape_text("a <b> & c") == "a &lt;b&gt; &amp; c"


def test_format_catalog_entry_preserves_long_description() -> None:
    desc = "x" * 520 + " <tag>"
    line = format_catalog_entry("demo", desc)
    assert line.startswith("- `demo`: ")
    assert "..." not in line
    assert "&lt;tag&gt;" in line
    assert len(line) > 520


def test_format_catalog_entries() -> None:
    manifests = [
        AgentSkillManifest(
            name="b-skill",
            description="second",
            location="/mnt/skills/public/b-skill/SKILL.md",
        ),
        AgentSkillManifest(
            name="a-skill",
            description="first",
            location="/mnt/skills/public/a-skill/SKILL.md",
        ),
    ]
    lines = format_catalog_entries(manifests)
    assert lines == ["- `b-skill`: second", "- `a-skill`: first"]


def test_resource_base_from_location() -> None:
    assert (
        resource_base_from_location("/mnt/skills/public/demo/SKILL.md")
        == "/mnt/skills/public/demo"
    )


def test_render_skill_content_with_directory_base() -> None:
    rendered = render_skill_content(
        name="demo",
        content="# Hello\n\nBody",
        resource_base="/mnt/skills/public/demo",
    )
    assert rendered.startswith('<skill_content name="demo">')
    assert "Base directory for this skill: /mnt/skills/public/demo" in rendered
    assert "<skill_instructions>" in rendered
    assert "# Hello\n\nBody" in rendered
    assert rendered.endswith("</skill_content>")

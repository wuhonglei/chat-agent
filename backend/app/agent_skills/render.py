"""Model-facing skill catalog and load-result rendering."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.agent_skills.types import AgentSkillManifest

_WS_RE = re.compile(r"\s+")


def escape_text(value: str) -> str:
    """Escape prose embedded inside skill markup framing tags."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_attr(value: str) -> str:
    """Escape a value used inside an XML attribute."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def normalize_catalog_description(value: str) -> str:
    """Whitespace-normalize a catalog description; full text, no truncation."""
    return _WS_RE.sub(" ", value).strip()


def format_catalog_entry(name: str, description: str) -> str:
    """One model-facing catalog line: ``- `name`: description``."""
    desc = escape_text(normalize_catalog_description(description))
    return f"- `{name}`: {desc}"


def format_catalog_entries(manifests: Sequence[AgentSkillManifest]) -> list[str]:
    """Render catalog lines from manifests (name + description only)."""
    return [format_catalog_entry(m.name, m.description) for m in manifests]


def resource_base_from_location(location: str) -> str:
    """Skill directory virtual path from a SKILL.md location."""
    loc = location.rstrip("/")
    if loc.endswith("/SKILL.md"):
        return loc[: -len("/SKILL.md")]
    if loc.endswith("SKILL.md"):
        return loc[: -len("SKILL.md")].rstrip("/")
    return loc


def render_skill_content(
    *,
    name: str,
    content: str,
    resource_base: str | None,
    provider: str = "filesystem",
) -> str:
    """Render the canonical ``<skill_content>`` block for the model / UI."""
    if resource_base:
        resource_lines = [
            f"Base directory for this skill: {escape_text(resource_base)}",
            "Resolve relative paths mentioned by this skill against the base "
            "directory before using them. Load referenced resources only as needed.",
        ]
    else:
        resource_lines = [
            f'Resources for this skill are managed by provider "{escape_text(provider)}".',
            "Load referenced resources only as needed.",
        ]
    return "\n".join(
        [
            f'<skill_content name="{escape_attr(name)}">',
            "<skill_resources>",
            *resource_lines,
            "</skill_resources>",
            "",
            "<skill_instructions>",
            content,
            "</skill_instructions>",
            "</skill_content>",
        ]
    )

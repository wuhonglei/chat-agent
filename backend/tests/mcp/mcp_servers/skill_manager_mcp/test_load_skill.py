"""Tests for load_skill MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent_skills.registry import AgentSkillRegistry, invalidate_skill_registry
from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.skill_manager_mcp.load_skill import LoadSkillTool
from app.vfs import paths as paths_module
from app.vfs.paths import Paths


def _write_skill(skill_dir: Path, name: str, description: str, body: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_load_skill_returns_skill_content_xml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public_dir = tmp_path / "public"
    _write_skill(public_dir / "demo", "demo", "a demo", "# Demo body")

    registry = AgentSkillRegistry(skills_dirs=[str(public_dir)])
    monkeypatch.setattr(
        "app.agent_skills.get_skill_registry",
        lambda _user_id=None: registry,
    )

    tool = LoadSkillTool()
    result = await tool.execute({"name": "demo"}, ToolContext())
    assert result.is_error is False
    assert '<skill_content name="demo">' in result.content
    assert "Base directory for this skill: /mnt/skills/public/demo" in result.content
    assert "# Demo body" in result.content
    assert result.structured_content is None


@pytest.mark.asyncio
async def test_load_skill_unknown_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public_dir = tmp_path / "skills_public"
    public_dir.mkdir()
    registry = AgentSkillRegistry(skills_dirs=[str(public_dir)])
    monkeypatch.setattr(
        "app.agent_skills.get_skill_registry",
        lambda _user_id=None: registry,
    )

    tool = LoadSkillTool()
    result = await tool.execute({"name": "missing"}, ToolContext())
    assert result.is_error is True
    assert 'skill "missing" is unknown or no longer available' in result.content


@pytest.mark.asyncio
async def test_load_skill_requires_name() -> None:
    tool = LoadSkillTool()
    result = await tool.execute({}, ToolContext())
    assert result.is_error is True
    assert result.content == "Error: name is required"


def test_registry_load_rereads_disk(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    skill_path = public_dir / "demo"
    _write_skill(skill_path, "demo", "v1", "# Version 1")
    registry = AgentSkillRegistry(skills_dirs=[str(public_dir)])
    first = registry.load("demo")
    assert "# Version 1" in first.body

    _write_skill(skill_path, "demo", "v2", "# Version 2")
    second = registry.load("demo")
    assert "# Version 2" in second.body
    assert second.manifest.description == "v2"
    assert second.manifest.location == "/mnt/skills/public/demo/SKILL.md"


def test_invalidate_skill_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_data = tmp_path / "user_data"
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    paths_module._paths = Paths(base_dir=user_data)
    monkeypatch.setattr(
        "app.agent_skills.registry.SKILLS_PUBLIC_DIR",
        public_dir,
    )
    try:
        invalidate_skill_registry()
        from app.agent_skills import get_skill_registry

        r1 = get_skill_registry(None)
        r2 = get_skill_registry(None)
        assert r1 is r2
        invalidate_skill_registry()
        r3 = get_skill_registry(None)
        assert r3 is not r1
    finally:
        invalidate_skill_registry()
        paths_module._paths = None

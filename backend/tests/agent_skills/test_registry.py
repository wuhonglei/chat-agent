"""Tests for per-user skill registry merging."""

from __future__ import annotations

from pathlib import Path

from app.agent_skills.registry import AgentSkillRegistry
from app.vfs import paths as paths_module
from app.vfs.paths import Paths


def _write_skill(skill_dir: Path, name: str, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_registry_merges_public_and_custom(tmp_path: Path) -> None:
    user_data = tmp_path / "user_data"
    public_dir = tmp_path / "skills_public"
    _write_skill(public_dir / "shared-skill", "shared-skill", "public version")

    user_skills = user_data / "user-1" / "skills"
    _write_skill(user_skills / "user-only", "user-only", "custom only")
    _write_skill(user_skills / "shared-skill", "shared-skill", "custom override")

    paths_module._paths = Paths(base_dir=user_data)
    try:
        registry = AgentSkillRegistry(
            skills_dirs=[str(public_dir), str(user_skills)],
        )
        manifests = {m.name: m for m in registry.list_manifests()}
        assert "user-only" in manifests
        assert (
            manifests["user-only"].location == "/mnt/skills/custom/user-only/SKILL.md"
        )
        assert manifests["shared-skill"].location == (
            "/mnt/skills/custom/shared-skill/SKILL.md"
        )
        assert manifests["shared-skill"].description == "custom override"
    finally:
        paths_module._paths = None


def test_registry_public_only_without_user_id(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    _write_skill(public_dir / "builtin", "builtin", "built-in skill")

    registry = AgentSkillRegistry(skills_dirs=[str(public_dir)])
    manifests = registry.list_manifests()
    assert len(manifests) == 1
    assert manifests[0].location == "/mnt/skills/public/builtin/SKILL.md"

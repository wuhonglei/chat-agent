"""Tests for skill system prompt catalog injection."""

from __future__ import annotations

from app.agent_skills.types import AgentSkillManifest
from app.prompts.prompt_utils import get_system_prompt_for_chat_session


def test_agent_mode_system_prompt_catalog_is_line_format() -> None:
    manifests = [
        AgentSkillManifest(
            name="demo-skill",
            description='Use when <demo> & "test"',
            location="/mnt/skills/public/demo-skill/SKILL.md",
        )
    ]
    prompt = get_system_prompt_for_chat_session(
        agent_mode=1,
        skill_manifests=manifests,
    )
    assert "<available_skills>" in prompt
    assert "- `demo-skill`:" in prompt
    assert "&lt;demo&gt;" in prompt
    assert "&amp;" in prompt
    assert "<location>" not in prompt
    assert "<name>demo-skill</name>" not in prompt
    assert "skill_manager_load_skill" in prompt
    assert "/mnt/skills/public/demo-skill/SKILL.md" not in prompt
    assert "未加载前不要根据摘要推断" in prompt


def test_agent_mode_0_omits_skill_system() -> None:
    prompt = get_system_prompt_for_chat_session(agent_mode=0, skill_manifests=[])
    assert "<skill_system>" not in prompt
    assert "<available_skills>" not in prompt

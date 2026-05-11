from __future__ import annotations

from typing import Any, cast

from app.agents.tool_executor import ToolExecutor


class _FakeMCPManager:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self._mapping = mapping

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self._mapping.get(tool_name)


def test_inject_workspace_args_for_agent_skills_overrides_model_args() -> None:
    manager = cast(
        Any, _FakeMCPManager({"write_workspace_file": "agent-skills-mcp"})
    )
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")
    executor.reset_for_request(
        user_message="message",
        user_id="trusted-user",
        workspace_id="trusted-workspace",
    )

    arguments = {
        "user_id": "forged-user",
        "workspace_id": "forged-workspace",
        "path": "index.tsx",
    }
    executor._inject_workspace_args_for_agent_skills(
        tool_name="write_workspace_file",
        arguments=arguments,
    )

    assert arguments["user_id"] == "trusted-user"
    assert arguments["workspace_id"] == "trusted-workspace"


def test_inject_workspace_args_for_agent_skills_requires_workspace_id() -> None:
    manager = cast(
        Any, _FakeMCPManager({"write_workspace_file": "agent-skills-mcp"})
    )
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")
    executor.reset_for_request(
        user_message="message",
        user_id="trusted-user",
        workspace_id=None,
    )

    try:
        executor._inject_workspace_args_for_agent_skills(
            tool_name="write_workspace_file",
            arguments={},
        )
    except ValueError as exc:
        assert str(exc) == "current workspace_id is required for workspace tools"
    else:
        raise AssertionError("expected ValueError when workspace_id is missing")


def test_inject_workspace_args_for_agent_skills_skips_non_workspace_tool() -> None:
    manager = cast(Any, _FakeMCPManager({"load_skill": "agent-skills-mcp"}))
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")
    executor.reset_for_request(
        user_message="message",
        user_id="trusted-user",
        workspace_id="trusted-workspace",
    )

    arguments = {"name": "frontend-project-templates"}
    executor._inject_workspace_args_for_agent_skills(
        tool_name="load_skill",
        arguments=arguments,
    )

    assert arguments == {"name": "frontend-project-templates"}

from __future__ import annotations

from typing import Any, cast

from app.agents.tool_executor import ToolExecutor


class _FakeMCPManager:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self._mapping = mapping

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self._mapping.get(tool_name)


def test_reset_for_request_sets_contextvars() -> None:
    manager = cast(Any, _FakeMCPManager({}))
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")

    from app.utils.logger import conversation_id_var, user_id_var

    executor.reset_for_request(
        user_message="message",
        user_id="test-user",
        workspace_id="test-workspace",
    )

    assert user_id_var.get() == "test-user"
    assert conversation_id_var.get() == "test-workspace"


def test_reset_for_request_with_none_values() -> None:
    manager = cast(Any, _FakeMCPManager({}))
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")

    from app.utils.logger import conversation_id_var, user_id_var

    # Reset to None
    user_id_var.set(None)
    conversation_id_var.set(None)

    executor.reset_for_request(
        user_message="message",
        user_id=None,
        workspace_id=None,
    )

    assert user_id_var.get() is None
    assert conversation_id_var.get() is None

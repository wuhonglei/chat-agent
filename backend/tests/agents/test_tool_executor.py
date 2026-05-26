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

    from app.utils.context import get_request_context

    executor.reset_for_request(
        user_message="message",
        user_id="test-user",
        conversation_id="test-conversation",
    )

    ctx = get_request_context()
    assert ctx.user_id == "test-user"
    assert ctx.conversation_id == "test-conversation"


def test_reset_for_request_with_none_values() -> None:
    manager = cast(Any, _FakeMCPManager({}))
    executor = ToolExecutor(manager, "message", "gpt-4o-mini")

    from app.utils.context import get_request_context, reset_request_context

    # Reset to clean state
    reset_request_context()

    executor.reset_for_request(
        user_message="message",
        user_id=None,
        conversation_id=None,
    )

    ctx = get_request_context()
    assert ctx.user_id is None
    assert ctx.conversation_id is None

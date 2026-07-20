"""ToolExecutor tool_success score 埋点测试。"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.agents import tool_executor as tool_executor_module
from app.agents.tool_executor import ToolExecutor


class _FakeSpan:
    def __init__(self) -> None:
        self.scores: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    def score(self, **kwargs: Any) -> None:
        self.scores.append(kwargs)

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class _FakeResult:
    structured_content = None


@pytest.fixture
def tool_call() -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id="call_1",
        type="function",
        function=Function(name="weather_get", arguments='{"city":"Shanghai"}'),
    )


@pytest.mark.asyncio
async def test_execute_single_tool_scores_success(
    monkeypatch: pytest.MonkeyPatch,
    tool_call: ChatCompletionMessageFunctionToolCall,
) -> None:
    span = _FakeSpan()

    class _FakeCM:
        def __enter__(self) -> _FakeSpan:
            return span

        def __exit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )

    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value=(_FakeResult(), []))
    manager.format_mcp_result.return_value = "ok"
    manager.get_server_for_tool.return_value = "weather"

    executor = ToolExecutor(cast(Any, manager), "天气怎么样", "gpt-4o-mini", 131072)
    monkeypatch.setattr(
        executor,
        "_compact_tool_result_if_needed",
        AsyncMock(side_effect=lambda msg: msg),
    )

    result = await executor.execute_single_tool(
        tool_call=tool_call,
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *args: None,
        on_urls_extracted=lambda urls: None,
    )

    assert result.is_error is False
    assert span.scores == [
        {
            "name": "tool_success",
            "value": True,
            "data_type": "BOOLEAN",
        }
    ]


@pytest.mark.asyncio
async def test_execute_single_tool_scores_empty_result_as_failure(
    monkeypatch: pytest.MonkeyPatch,
    tool_call: ChatCompletionMessageFunctionToolCall,
) -> None:
    span = _FakeSpan()

    class _FakeCM:
        def __enter__(self) -> _FakeSpan:
            return span

        def __exit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )

    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value=(_FakeResult(), []))
    manager.format_mcp_result.return_value = ""
    manager.get_server_for_tool.return_value = "weather"

    executor = ToolExecutor(cast(Any, manager), "天气怎么样", "gpt-4o-mini", 131072)
    monkeypatch.setattr(
        executor,
        "_compact_tool_result_if_needed",
        AsyncMock(side_effect=lambda msg: msg),
    )

    result = await executor.execute_single_tool(
        tool_call=tool_call,
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *args: None,
        on_urls_extracted=lambda urls: None,
    )

    assert result.is_error is True
    assert span.scores == [
        {
            "name": "tool_success",
            "value": False,
            "data_type": "BOOLEAN",
            "comment": "empty_result",
            "metadata": {"error_type": "empty_result"},
        }
    ]


@pytest.mark.asyncio
async def test_execute_single_tool_scores_shell_by_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tool_call: ChatCompletionMessageFunctionToolCall,
) -> None:
    span = _FakeSpan()

    class _FakeCM:
        def __enter__(self) -> _FakeSpan:
            return span

        def __exit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )

    class _ShellResult:
        structured_content = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "fail",
            "blocked": False,
            "timed_out": False,
        }

    shell_call = ChatCompletionMessageFunctionToolCall(
        id="call_shell",
        type="function",
        function=Function(name="shell_exec", arguments='{"command":"false"}'),
    )

    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value=(_ShellResult(), []))
    manager.format_mcp_result.return_value = "$ false\n[exit_code=1]\nfail"
    manager.get_server_for_tool.return_value = "shell"

    executor = ToolExecutor(cast(Any, manager), "run false", "gpt-4o-mini", 131072)
    monkeypatch.setattr(
        tool_executor_module,
        "build_shell_display_items",
        lambda structured: [{"type": "shell_exec", **structured}],
    )

    result = await executor.execute_single_tool(
        tool_call=shell_call,
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *args: None,
        on_urls_extracted=lambda urls: None,
    )

    assert result.is_error is True
    assert span.scores == [
        {
            "name": "tool_success",
            "value": False,
            "data_type": "BOOLEAN",
            "comment": "non_zero_exit",
            "metadata": {"error_type": "non_zero_exit", "exit_code": 1},
        }
    ]


@pytest.mark.asyncio
async def test_execute_single_tool_scores_exception_as_failure(
    monkeypatch: pytest.MonkeyPatch,
    tool_call: ChatCompletionMessageFunctionToolCall,
) -> None:
    span = _FakeSpan()

    class _FakeCM:
        def __enter__(self) -> _FakeSpan:
            return span

        def __exit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )

    manager = MagicMock()
    manager.call_tool = AsyncMock(side_effect=RuntimeError("mcp down"))
    manager.get_server_for_tool.return_value = "weather"

    executor = ToolExecutor(cast(Any, manager), "天气怎么样", "gpt-4o-mini", 131072)

    result = await executor.execute_single_tool(
        tool_call=tool_call,
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *args: None,
        on_urls_extracted=lambda urls: None,
    )

    assert result.is_error is True
    assert span.scores == [
        {
            "name": "tool_success",
            "value": False,
            "data_type": "BOOLEAN",
            "comment": "RuntimeError",
            "metadata": {"error_type": "RuntimeError"},
        }
    ]

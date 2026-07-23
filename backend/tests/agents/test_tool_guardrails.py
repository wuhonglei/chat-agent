"""Tests for ToolCallGuardrail and executor integration."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.agents import tool_executor as tool_executor_module
from app.agents.tool_call_guardrail import GuardrailDecisionKind, ToolCallGuardrail
from app.agents.tool_executor import ToolExecutor
from app.mcp.constants import READ_FILE_LLM, SHELL_LLM, WRITE_FILE_LLM


class _FakeSpan:
    def score(self, **kwargs: Any) -> None:
        return None

    def update(self, **kwargs: Any) -> None:
        return None


class _FakeCM:
    def __enter__(self) -> _FakeSpan:
        return _FakeSpan()

    def __exit__(self, *args: Any) -> None:
        return None


class _FakeResult:
    structured_content = None


def _tc(
    name: str, arguments: str, call_id: str = "call_1"
) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id=call_id,
        type="function",
        function=Function(name=name, arguments=arguments),
    )


def test_exact_failure_warn_and_block() -> None:
    g = ToolCallGuardrail(exact_failure_warn_after=2, exact_failure_block_after=5)
    args = {"file_path": "/missing"}

    for i in range(5):
        decision = g.before_call(READ_FILE_LLM, args)
        assert decision.kind == GuardrailDecisionKind.ALLOW
        suffix = g.record_outcome(
            tool_name=READ_FILE_LLM,
            arguments=args,
            success=False,
            content="Error: not found",
        )
        if i + 1 >= 2:
            assert "连续失败" in suffix

    decision = g.before_call(READ_FILE_LLM, args)
    assert decision.kind == GuardrailDecisionKind.BLOCK
    assert "已阻断" in decision.message


def test_exact_failure_resets_on_success() -> None:
    g = ToolCallGuardrail(exact_failure_block_after=5)
    args = {"file_path": "/missing"}
    for _ in range(4):
        g.record_outcome(
            tool_name=READ_FILE_LLM,
            arguments=args,
            success=False,
            content="err",
        )
    g.record_outcome(
        tool_name=READ_FILE_LLM,
        arguments=args,
        success=True,
        content="ok",
    )
    assert g.before_call(READ_FILE_LLM, args).kind == GuardrailDecisionKind.ALLOW


def test_same_tool_halt_and_clear_on_success() -> None:
    g = ToolCallGuardrail(
        same_tool_failure_warn_after=3,
        same_tool_failure_halt_after=8,
    )
    for i in range(8):
        g.record_outcome(
            tool_name=SHELL_LLM,
            arguments={"command": f"cmd-{i}"},
            success=False,
            content="err",
        )
    assert g.halted is True

    g2 = ToolCallGuardrail(same_tool_failure_halt_after=8)
    for i in range(7):
        g2.record_outcome(
            tool_name=SHELL_LLM,
            arguments={"command": f"cmd-{i}"},
            success=False,
            content="err",
        )
    g2.record_outcome(
        tool_name=SHELL_LLM,
        arguments={"command": "ok"},
        success=True,
        content="done",
    )
    assert g2.halted is False
    assert g2.before_call(SHELL_LLM, {"command": "x"}).kind == GuardrailDecisionKind.ALLOW


def test_no_progress_blocks_idempotent_only() -> None:
    g = ToolCallGuardrail(no_progress_warn_after=3, no_progress_block_after=5)
    args = {"file_path": "/mnt/user-data/workspace/a.txt"}
    for i in range(5):
        suffix = g.record_outcome(
            tool_name=READ_FILE_LLM,
            arguments=args,
            success=True,
            content="same-content",
        )
        if i + 1 >= 3:
            assert "相同结果" in suffix

    decision = g.before_call(READ_FILE_LLM, args)
    assert decision.kind == GuardrailDecisionKind.BLOCK

    g_mut = ToolCallGuardrail(no_progress_block_after=5)
    write_args = {"file_path": "/mnt/user-data/workspace/a.txt", "content": "x"}
    for _ in range(5):
        g_mut.record_outcome(
            tool_name=WRITE_FILE_LLM,
            arguments=write_args,
            success=True,
            content="File written",
        )
    assert (
        g_mut.before_call(WRITE_FILE_LLM, write_args).kind == GuardrailDecisionKind.ALLOW
    )


def test_reset_clears_state() -> None:
    g = ToolCallGuardrail()
    g.record_outcome(
        tool_name=READ_FILE_LLM,
        arguments={"file_path": "a"},
        success=False,
        content="err",
    )
    g.halted = True
    g.reset()
    assert g.halted is False
    assert g.before_call(READ_FILE_LLM, {"file_path": "a"}).kind == GuardrailDecisionKind.ALLOW


@pytest.mark.asyncio
async def test_executor_blocks_exact_failure_without_calling_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )
    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value=(_FakeResult(), []))
    manager.format_mcp_result.return_value = "Error: not found"
    manager.get_server_for_tool.return_value = "file"

    executor = ToolExecutor(cast(Any, manager), "read", "gpt-4o-mini", 131072)
    monkeypatch.setattr(
        executor,
        "_compact_tool_result_if_needed",
        AsyncMock(side_effect=lambda msg: msg),
    )
    # Force outcome to failure for file server empty-like errors
    monkeypatch.setattr(
        ToolExecutor,
        "_resolve_tool_outcome",
        staticmethod(lambda **kwargs: (False, "execution_error", {})),
    )

    args = '{"file_path":"/missing"}'
    for i in range(5):
        await executor.execute_single_tool(
            tool_call=_tc(READ_FILE_LLM, args, call_id=f"c{i}"),
            current_iteration=0,
            extracted_urls=set(),
            on_arguments_recorded=lambda *a: None,
        )

    assert manager.call_tool.await_count == 5

    blocked = await executor.execute_single_tool(
        tool_call=_tc(READ_FILE_LLM, args, call_id="c_block"),
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *a: None,
    )
    assert blocked.is_error is True
    assert "已阻断" in (blocked.content or "")
    assert manager.call_tool.await_count == 5


@pytest.mark.asyncio
async def test_executor_skips_remaining_segment_after_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tool_executor_module,
        "observation_span",
        lambda *args, **kwargs: _FakeCM(),
    )
    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value=(_FakeResult(), []))
    manager.format_mcp_result.return_value = "err"
    manager.get_server_for_tool.return_value = "shell"

    executor = ToolExecutor(cast(Any, manager), "shell", "gpt-4o-mini", 131072)
    executor.guardrail.same_tool_failure_halt_after = 1
    monkeypatch.setattr(
        ToolExecutor,
        "_resolve_tool_outcome",
        staticmethod(lambda **kwargs: (False, "non_zero_exit", {})),
    )

    # Trigger halt on first shell failure.
    await executor.execute_single_tool(
        tool_call=_tc(SHELL_LLM, '{"command":"false","description":"fail"}', "c0"),
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *a: None,
    )
    assert executor.guardrail.halted is True
    assert manager.call_tool.await_count == 1

    # Later segment/batch must not call MCP.
    results = await executor.execute_tool_calls_parallel(
        tool_calls=[
            _tc(
                WRITE_FILE_LLM,
                '{"file_path":"/mnt/user-data/workspace/a.txt","content":"x"}',
                "c2",
            ),
        ],
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *a: None,
    )
    assert len(results) == 1
    assert results[0].is_error is True
    assert "熔断" in (results[0].content or "")
    assert manager.call_tool.await_count == 1

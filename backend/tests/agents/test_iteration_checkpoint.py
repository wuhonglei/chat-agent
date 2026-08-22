"""Agent 模式轮次检查点与 task_action 预算解析测试。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat_session_agent import ChatSessionAgent
from app.agents.mcp_tool_execution import MCPToolSession
from app.mcp.constants import WEB_SEARCH_LLM
from app.prompts.prompt_utils import (
    get_continue_task_notice,
    get_iteration_checkpoint_notice,
    get_summarize_task_notice,
)
from app.schemas.chat import ChatRequest, TextBlock
from app.schemas.config import ChatContextConfig, LLMConfig
from app.services.chat.history_context_service import HistoryContextService
from app.utils.common import gen_uuid
from app.utils.token import TokenCalculator


def _llm() -> LLMConfig:
    return LLMConfig(
        api_key="k",
        api_base="https://example.com/v1",
        model_name="test",
        context_limit=128_000,
        max_output_tokens=8192,
    )


def _agent() -> ChatSessionAgent:
    calc = TokenCalculator(model="gpt-4o", context_limit=128_000)
    history = HistoryContextService(ChatContextConfig(), calc)
    mcp = MagicMock()
    mcp.get_tool_route = MagicMock(return_value=None)
    return ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(),
        mcp_manager=mcp,
        history_context_service=history,
        chat_context_config=ChatContextConfig(),
    )


def test_resolve_max_tool_iterations_by_mode_and_action() -> None:
    assert (
        ChatSessionAgent.resolve_max_tool_iterations(agent_mode=0, task_action=None)
        == MCPToolSession.MAX_TOTAL_ITERATIONS
    )
    assert (
        ChatSessionAgent.resolve_max_tool_iterations(
            agent_mode=0, task_action="continue"
        )
        == MCPToolSession.MAX_TOTAL_ITERATIONS
    )
    assert (
        ChatSessionAgent.resolve_max_tool_iterations(agent_mode=1, task_action=None)
        == MCPToolSession.AGENT_MODE_MAX_ITERATIONS
    )
    assert (
        ChatSessionAgent.resolve_max_tool_iterations(
            agent_mode=1, task_action="continue"
        )
        == MCPToolSession.CONTINUE_BUDGET_ITERATIONS
    )
    assert (
        ChatSessionAgent.resolve_max_tool_iterations(
            agent_mode=1, task_action="summarize"
        )
        == MCPToolSession.AGENT_MODE_MAX_ITERATIONS
    )


def test_iteration_checkpoint_notice_renders_count() -> None:
    text = get_iteration_checkpoint_notice(iterations_used=90)
    assert "90" in text
    assert "是否继续" in text
    assert "不要再调用" in text


def test_continue_and_summarize_notices() -> None:
    cont = get_continue_task_notice(continue_budget=50)
    assert "50" in cont
    assert "继续" in cont
    summary = get_summarize_task_notice()
    assert "总结" in summary
    assert "勿再调用" in summary


def _chat_request(*, agent_mode: int, task_action: str | None = None) -> ChatRequest:
    return ChatRequest(
        content_blocks=[TextBlock(id=gen_uuid(), text="做一个复杂任务")],
        conversation_id=gen_uuid(),
        agent_mode=agent_mode,
        task_action=task_action,  # type: ignore[arg-type]
        think_mode=False,
        model_id="",
    )


@pytest.mark.asyncio
async def test_agent_mode_max_iterations_sets_checkpoint() -> None:
    agent = _agent()
    tools = [{"type": "function", "function": {"name": "file_write", "parameters": {}}}]
    agent.mcp_manager.get_tools_for_llm = AsyncMock(return_value=tools)

    async def _fake_guard(**kwargs: Any) -> tuple[str, list[dict[str, Any]]]:
        return "ok", kwargs["base_prompt_messages"]

    agent.unified_context_guard = AsyncMock(side_effect=_fake_guard)  # type: ignore[method-assign]

    captured: dict[str, Any] = {}

    async def _fake_final(
        *,
        messages: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        final_user_message: str | None = None,
        extra_notice: str | None = None,
        extra_plugin: str = "iteration_checkpoint",
    ) -> AsyncGenerator[str, None]:
        captured["extra_notice"] = extra_notice
        captured["extra_plugin"] = extra_plugin
        captured["iteration"] = iteration
        yield "event: content_block\ndata: {}\n\n"

    agent._stream_final_round_events = _fake_final  # type: ignore[method-assign]

    async def _fake_tool_round(
        round_prompt_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        round_state: Any,
    ) -> AsyncGenerator[str, None]:
        # 始终继续工具循环，直到耗尽预算
        round_state.is_final_answer_complete = False
        if False:  # pragma: no cover — keep async generator shape
            yield ""
        return

    agent._stream_tool_round_events = _fake_tool_round  # type: ignore[method-assign]

    with (
        patch.object(MCPToolSession, "AGENT_MODE_MAX_ITERATIONS", 2),
        patch(
            "app.agents.chat_session_agent.get_skill_registry",
            return_value=MagicMock(list_manifests=MagicMock(return_value=[])),
        ),
    ):
        events: list[str] = []
        async for sse in agent.stream_session_events(
            chat_request=_chat_request(agent_mode=1),
            history_messages=[],
            history_summary_before_window=None,
            conversation_id="c1",
            user_memories=[],
            user_id="u1",
        ):
            events.append(sse)

    assert agent.iteration_checkpoint is not None
    assert agent.iteration_checkpoint["iterations_used"] == 2
    assert (
        agent.iteration_checkpoint["continue_budget"]
        == MCPToolSession.CONTINUE_BUDGET_ITERATIONS
    )
    assert captured["extra_plugin"] == "iteration_checkpoint"
    assert captured["extra_notice"] is not None
    assert "2" in captured["extra_notice"]
    assert events


@pytest.mark.asyncio
async def test_normal_mode_max_iterations_no_checkpoint() -> None:
    agent = _agent()
    tools = [{"type": "function", "function": {"name": "web_search", "parameters": {}}}]
    agent.mcp_manager.get_tools_for_llm = AsyncMock(return_value=tools)

    async def _fake_guard(**kwargs: Any) -> tuple[str, list[dict[str, Any]]]:
        return "ok", kwargs["base_prompt_messages"]

    agent.unified_context_guard = AsyncMock(side_effect=_fake_guard)  # type: ignore[method-assign]

    captured: dict[str, Any] = {}

    async def _fake_final(
        *,
        messages: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        final_user_message: str | None = None,
        extra_notice: str | None = None,
        extra_plugin: str = "iteration_checkpoint",
    ) -> AsyncGenerator[str, None]:
        captured["extra_notice"] = extra_notice
        yield "event: content_block\ndata: {}\n\n"

    agent._stream_final_round_events = _fake_final  # type: ignore[method-assign]

    async def _fake_tool_round(
        round_prompt_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        round_state: Any,
    ) -> AsyncGenerator[str, None]:
        round_state.is_final_answer_complete = False
        if False:  # pragma: no cover
            yield ""
        return

    agent._stream_tool_round_events = _fake_tool_round  # type: ignore[method-assign]

    with patch.object(MCPToolSession, "MAX_TOTAL_ITERATIONS", 2):
        async for _ in agent.stream_session_events(
            chat_request=_chat_request(agent_mode=0),
            history_messages=[],
            history_summary_before_window=None,
            conversation_id="c1",
            user_memories=[],
            user_id="u1",
        ):
            pass

    assert agent.iteration_checkpoint is None
    assert captured["extra_notice"] is None


@pytest.mark.asyncio
async def test_summarize_task_action_skips_tool_loop() -> None:
    agent = _agent()
    tools = [{"type": "function", "function": {"name": "file_write", "parameters": {}}}]
    agent.mcp_manager.get_tools_for_llm = AsyncMock(return_value=tools)

    async def _fake_guard(**kwargs: Any) -> tuple[str, list[dict[str, Any]]]:
        return "ok", kwargs["base_prompt_messages"]

    agent.unified_context_guard = AsyncMock(side_effect=_fake_guard)  # type: ignore[method-assign]

    tool_round_called = False
    captured: dict[str, Any] = {}

    async def _fake_tool_round(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
        nonlocal tool_round_called
        tool_round_called = True
        if False:  # pragma: no cover
            yield ""
        return

    async def _fake_final(
        *,
        messages: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        final_user_message: str | None = None,
        extra_notice: str | None = None,
        extra_plugin: str = "iteration_checkpoint",
    ) -> AsyncGenerator[str, None]:
        captured["extra_plugin"] = extra_plugin
        captured["extra_notice"] = extra_notice
        yield "ok"

    agent._stream_tool_round_events = _fake_tool_round  # type: ignore[method-assign]
    agent._stream_final_round_events = _fake_final  # type: ignore[method-assign]

    with patch(
        "app.agents.chat_session_agent.get_skill_registry",
        return_value=MagicMock(list_manifests=MagicMock(return_value=[])),
    ):
        async for _ in agent.stream_session_events(
            chat_request=_chat_request(agent_mode=1, task_action="summarize"),
            history_messages=[],
            history_summary_before_window=None,
            conversation_id="c1",
            user_memories=[],
            user_id="u1",
        ):
            pass

    assert tool_round_called is False
    assert captured["extra_plugin"] == "summarize_task"
    assert captured["extra_notice"] is not None
    assert "总结" in captured["extra_notice"]


@pytest.mark.asyncio
async def test_continue_task_action_uses_continue_budget() -> None:
    agent = _agent()
    tools = [{"type": "function", "function": {"name": "file_write", "parameters": {}}}]
    agent.mcp_manager.get_tools_for_llm = AsyncMock(return_value=tools)

    async def _fake_guard(**kwargs: Any) -> tuple[str, list[dict[str, Any]]]:
        return "ok", kwargs["base_prompt_messages"]

    agent.unified_context_guard = AsyncMock(side_effect=_fake_guard)  # type: ignore[method-assign]

    iterations_seen: list[int] = []
    first_round_has_continue_hint = False

    async def _fake_tool_round(
        round_prompt_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        tool_session: MCPToolSession,
        iteration: int,
        round_state: Any,
    ) -> AsyncGenerator[str, None]:
        nonlocal first_round_has_continue_hint
        iterations_seen.append(iteration)
        if iteration == 0:
            trailing = round_prompt_messages[-1] if round_prompt_messages else {}
            content = str(trailing.get("content") or "")
            first_round_has_continue_hint = "继续" in content or "剩余工作" in content
        # 耗尽 continue 预算才进检查点
        round_state.is_final_answer_complete = False
        if False:  # pragma: no cover
            yield ""
        return

    agent._stream_tool_round_events = _fake_tool_round  # type: ignore[method-assign]

    async def _fake_final(**kwargs: Any) -> AsyncGenerator[str, None]:
        yield "ok"

    agent._stream_final_round_events = _fake_final  # type: ignore[method-assign]

    with (
        patch.object(MCPToolSession, "CONTINUE_BUDGET_ITERATIONS", 3),
        patch(
            "app.agents.chat_session_agent.get_skill_registry",
            return_value=MagicMock(list_manifests=MagicMock(return_value=[])),
        ),
    ):
        async for _ in agent.stream_session_events(
            chat_request=_chat_request(agent_mode=1, task_action="continue"),
            history_messages=[],
            history_summary_before_window=None,
            conversation_id="c1",
            user_memories=[],
            user_id="u1",
        ):
            pass

    assert iterations_seen == [0, 1, 2]
    assert first_round_has_continue_hint is True
    assert agent.iteration_checkpoint is not None
    assert agent.iteration_checkpoint["iterations_used"] == 3


@pytest.mark.asyncio
async def test_final_round_omits_iteration_hints_and_guardrail_warns() -> None:
    agent = _agent()
    tool_session = MCPToolSession(
        agent.mcp_manager,
        "query",
        "test",
        128_000,
        [],
    )
    tool_session.reset_for_request("query", agent_mode=0)
    tool_session.policy.tool_arguments_history_by_name[WEB_SEARCH_LLM].extend(
        [
            {"arguments": {"q": "a"}, "tool_call_id": "c1", "success": True},
            {"arguments": {"q": "b"}, "tool_call_id": "c2", "success": True},
        ]
    )
    queued_hint = tool_session.policy.collect_iteration_hints()
    assert queued_hint is not None
    tool_session.refresh_iteration_hints_after_tools()
    tool_session.executor.guardrail.record_outcome(
        tool_name=WEB_SEARCH_LLM,
        arguments={"q": "a"},
        success=False,
        content="err",
    )
    tool_session.executor.guardrail.record_outcome(
        tool_name=WEB_SEARCH_LLM,
        arguments={"q": "a"},
        success=False,
        content="err",
    )

    captured: dict[str, Any] = {}

    async def _fake_tool_round(
        round_prompt_messages: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        _tool_session: MCPToolSession,
        iteration: int,
        round_state: Any,
    ) -> AsyncGenerator[str, None]:
        captured["prompts"] = round_prompt_messages
        captured["tools"] = available_tools
        round_state.is_final_answer_complete = True
        if False:  # pragma: no cover
            yield ""
        return

    agent._stream_tool_round_events = _fake_tool_round  # type: ignore[method-assign]

    extra = get_iteration_checkpoint_notice(iterations_used=10)
    events: list[str] = []
    async for sse in agent._stream_final_round_events(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ],
        tool_session=tool_session,
        iteration=10,
        extra_notice=extra,
        extra_plugin="iteration_checkpoint",
    ):
        events.append(sse)

    assert captured["tools"] == []
    trailing = captured["prompts"][-1]
    content = str(trailing.get("content") or "")
    assert extra in content
    assert queued_hint not in content
    assert "连续失败" not in content
    assert trailing["source"]["plugin"] == "iteration_checkpoint"
    assert tool_session.drain_pending_iteration_hints() is None
    assert tool_session.drain_pending_guardrail_warns() == []
    assert events

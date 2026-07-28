"""unified_context_guard 与相关原语单元测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.agents.chat_session_agent import ChatSessionAgent
from app.schemas.chat import ChatMessage, TextBlock
from app.schemas.config import (
    ChatContextConfig,
    LLMConfig,
    UnifiedContextGuardConfig,
    WindowOutSummaryConfig,
)
from app.schemas.llm import ToolResultMessage, ToolUseMessage
from app.services.chat.history_context_service import (
    HistoryContextService,
    tool_round_compressible_end,
)
from app.utils.history_truncate import split_history_by_token_budget
from app.utils.token import TokenCalculator


def _calc(limit: int = 128_000) -> TokenCalculator:
    return TokenCalculator(model="gpt-4o", context_limit=limit)


def _llm(limit: int = 128_000, max_out: int = 8192) -> LLMConfig:
    return LLMConfig(
        api_key="k",
        api_base="https://example.com/v1",
        model_name="test",
        context_limit=limit,
        max_output_tokens=max_out,
    )


def test_compute_context_threshold_formula() -> None:
    guard = UnifiedContextGuardConfig(buffer_tokens=13000, max_output_tokens=8192)
    threshold = HistoryContextService.compute_context_threshold(
        128_000, 8192, guard
    )
    assert threshold == 128_000 - 8192 - 13000


def test_compute_context_threshold_uses_min_of_model_and_guard_cap() -> None:
    guard = UnifiedContextGuardConfig(buffer_tokens=1000, max_output_tokens=8192)
    # model claims 16K output, guard caps at 8192
    threshold = HistoryContextService.compute_context_threshold(
        100_000, 16_384, guard
    )
    assert threshold == 100_000 - 8192 - 1000


def test_split_history_by_token_budget_keeps_newest_rounds() -> None:
    calc = _calc()
    messages: list[ChatMessage] = []
    for i in range(4):
        messages.append(
            ChatMessage(
                id=f"u{i}",
                conversation_id="c",
                role="user",
                content_blocks=[TextBlock(id=f"ut{i}", text="hi " * 200)],
                status="done",
            )
        )
        messages.append(
            ChatMessage(
                id=f"a{i}",
                conversation_id="c",
                role="assistant",
                content_blocks=[TextBlock(id=f"at{i}", text="ok " * 200)],
                status="done",
            )
        )
    # tiny budget → only newest round(s)
    in_window, out_of_window = split_history_by_token_budget(messages, 50, calc)
    assert in_window
    assert out_of_window
    assert in_window[-1].id == "a3"
    assert all(m.id not in {x.id for x in in_window} for m in out_of_window)


def test_compress_tool_round_messages_size_aware_prefers_largest() -> None:
    svc = HistoryContextService(
        ChatContextConfig(
            unified_guard=UnifiedContextGuardConfig(
                keep_recent_tool_results=2,
                tool_result_compress_threshold_chars=100,
                tool_result_compress_keep_head_chars=20,
                tool_result_compress_keep_tail_chars=20,
            )
        ),
        _calc(),
    )
    tool_call = ChatCompletionMessageFunctionToolCall(
        id="c1",
        type="function",
        function=Function(name="t", arguments="{}"),
    )
    rounds: list[Any] = [
        ToolUseMessage(
            role="assistant",
            content=None,
            reasoning_content=None,
            tool_calls=[tool_call],
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="c1",
            is_error=False,
            content="BIG" + ("X" * 5000),
        ),
        ToolUseMessage(
            role="assistant",
            content=None,
            reasoning_content=None,
            tool_calls=[tool_call],
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="c2",
            is_error=False,
            content="small-ok",
        ),
        ToolUseMessage(
            role="assistant",
            content=None,
            reasoning_content=None,
            tool_calls=[tool_call],
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="c3",
            is_error=False,
            content="keep-recent-full" + ("Y" * 2000),
        ),
    ]
    changed = svc.compress_tool_round_messages(rounds)
    assert changed is True
    # last 2 ToolUse+results groups kept intact (keep_recent=2)
    assert "Y" * 100 in rounds[-1].content  # type: ignore[union-attr]
    assert rounds[3].content == "small-ok"  # type: ignore[union-attr]
    # large older-group result truncated
    assert "中间已省略" in rounds[1].content  # type: ignore[union-attr]


def test_compress_tool_round_messages_keeps_parallel_results_as_one_group() -> None:
    """一次 ToolUse 后的多条 ToolResult 同属一组，不被拆开保护。"""
    svc = HistoryContextService(
        ChatContextConfig(
            unified_guard=UnifiedContextGuardConfig(
                keep_recent_tool_results=1,
                tool_result_compress_threshold_chars=100,
                tool_result_compress_keep_head_chars=20,
                tool_result_compress_keep_tail_chars=20,
            )
        ),
        _calc(),
    )
    use_parallel = ToolUseMessage(
        role="assistant",
        content=None,
        reasoning_content=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="p1",
                type="function",
                function=Function(name="t1", arguments="{}"),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="p2",
                type="function",
                function=Function(name="t2", arguments="{}"),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="p3",
                type="function",
                function=Function(name="t3", arguments="{}"),
            ),
        ],
    )
    use_next = ToolUseMessage(
        role="assistant",
        content=None,
        reasoning_content=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="n1",
                type="function",
                function=Function(name="t4", arguments="{}"),
            )
        ],
    )
    rounds: list[Any] = [
        use_parallel,
        ToolResultMessage(
            role="tool",
            tool_call_id="p1",
            is_error=False,
            content="OLD1" + ("A" * 2000),
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="p2",
            is_error=False,
            content="OLD2" + ("B" * 2000),
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="p3",
            is_error=False,
            content="OLD3" + ("C" * 2000),
        ),
        use_next,
        ToolResultMessage(
            role="tool",
            tool_call_id="n1",
            is_error=False,
            content="KEEP" + ("D" * 2000),
        ),
    ]
    changed = svc.compress_tool_round_messages(rounds)
    assert changed is True
    # older parallel group: all three results compressible
    assert "中间已省略" in rounds[1].content  # type: ignore[union-attr]
    assert "中间已省略" in rounds[2].content  # type: ignore[union-attr]
    assert "中间已省略" in rounds[3].content  # type: ignore[union-attr]
    # newest group intact
    assert "D" * 100 in rounds[-1].content  # type: ignore[union-attr]


def test_tool_round_compressible_end_groups_parallel_batch() -> None:
    use = ToolUseMessage(
        role="assistant",
        content=None,
        reasoning_content=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="a",
                type="function",
                function=Function(name="t", arguments="{}"),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="b",
                type="function",
                function=Function(name="t", arguments="{}"),
            ),
        ],
    )
    messages: list[Any] = [
        use,
        ToolResultMessage(
            role="tool", tool_call_id="a", is_error=False, content="r1"
        ),
        ToolResultMessage(
            role="tool", tool_call_id="b", is_error=False, content="r2"
        ),
    ]
    # single group + keep 1 → nothing compressible
    assert tool_round_compressible_end(messages, 1) == 0
    assert tool_round_compressible_end(messages, 0) == 3


@pytest.mark.asyncio
async def test_unified_context_guard_noop_under_threshold() -> None:
    history_svc = HistoryContextService(ChatContextConfig(), _calc())
    agent = ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(),
        mcp_manager=MagicMock(),
        history_context_service=history_svc,
        chat_context_config=ChatContextConfig(),
    )
    agent._system_prompt = "sys"
    agent._working_history = []
    agent._user_message_content = "hello"
    agent._window_out_summary = None
    base = agent._compose_messages("sys", [], "hello", [])
    action, out = await agent.unified_context_guard(
        base_prompt_messages=base,
        conversation_id="conv",
        allow_stop_tools=True,
    )
    assert action == "ok"
    assert out == base


@pytest.mark.asyncio
async def test_unified_context_guard_stop_tools_when_still_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = UnifiedContextGuardConfig(
        buffer_tokens=100,
        max_output_tokens=100,
        keep_recent_tool_results=0,
    )
    cfg = ChatContextConfig(
        unified_guard=guard,
        window_out_summary=WindowOutSummaryConfig(enabled=False),
    )
    history_svc = HistoryContextService(cfg, _calc(limit=500))
    history_svc.compress_history_tool_results = lambda h: h  # type: ignore[method-assign]
    history_svc.split_by_remaining_budget = lambda h, b: (h, [])  # type: ignore[method-assign]
    monkeypatch.setattr(
        ChatSessionAgent,
        "_size_aware_compress_tool_rounds",
        lambda self, base, threshold, keep_recent=None: threshold + 1,
    )
    monkeypatch.setattr(
        TokenCalculator,
        "count_messages_tokens",
        lambda self, messages: 10_000,
    )
    monkeypatch.setattr(
        TokenCalculator,
        "count_message_tokens",
        lambda self, message: 100,
    )

    agent = ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(limit=500, max_out=100),
        mcp_manager=MagicMock(),
        history_context_service=history_svc,
        chat_context_config=cfg,
    )
    agent._system_prompt = "sys"
    agent._working_history = []
    agent._user_message_content = "hi"
    agent._user_message_text = "hi"
    agent._window_out_summary = None
    agent._kb_context_blocks = None
    agent._user_memories = []
    agent._attachment_uploads = None
    base = agent._compose_messages("sys", [], "hi", [])
    action, _ = await agent.unified_context_guard(
        base_prompt_messages=base,
        conversation_id="conv",
        allow_stop_tools=True,
    )
    assert action == "stop_tools"


def test_size_aware_compress_respects_keep_recent_then_zero() -> None:
    """Step 4: keep_recent protects latest group; keep_recent=0 can shrink it."""
    guard = UnifiedContextGuardConfig(
        keep_recent_tool_results=2,
        tool_result_compress_threshold_chars=100,
        tool_result_compress_keep_head_chars=20,
        tool_result_compress_keep_tail_chars=20,
    )
    cfg = ChatContextConfig(unified_guard=guard)
    agent = ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(),
        mcp_manager=MagicMock(),
        history_context_service=HistoryContextService(cfg, _calc()),
        chat_context_config=cfg,
    )
    tool_call = ChatCompletionMessageFunctionToolCall(
        id="c1",
        type="function",
        function=Function(name="t", arguments="{}"),
    )
    recent_content = "RECENT" + ("Y" * 2000)
    agent.session_output.tool_round_messages = [
        ToolUseMessage(
            role="assistant",
            content=None,
            reasoning_content=None,
            tool_calls=[tool_call],
        ),
        ToolResultMessage(
            role="tool",
            tool_call_id="c1",
            is_error=False,
            content=recent_content,
        ),
    ]
    base = [{"role": "user", "content": "hi"}]

    # With default keep_recent=2 and only one group → nothing compressible.
    tokens_after_keep = agent._size_aware_compress_tool_rounds(base, threshold=1)
    assert agent.session_output.tool_round_messages[1].content == recent_content  # type: ignore[union-attr]
    assert tokens_after_keep > 0

    # Escalation keep_recent=0 compresses the latest (only) group.
    agent._size_aware_compress_tool_rounds(base, threshold=1, keep_recent=0)
    compressed = agent.session_output.tool_round_messages[1].content  # type: ignore[union-attr]
    assert compressed != recent_content
    assert "中间已省略" in compressed
    assert compressed.startswith("RECENT")


@pytest.mark.asyncio
async def test_unified_context_guard_escalates_keep_recent_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Step 4 with keep_recent still over, guard retries with keep_recent=0."""
    guard = UnifiedContextGuardConfig(
        buffer_tokens=100,
        max_output_tokens=100,
        keep_recent_tool_results=2,
        tool_result_compress_threshold_chars=100,
        tool_result_compress_keep_head_chars=20,
        tool_result_compress_keep_tail_chars=20,
    )
    cfg = ChatContextConfig(
        unified_guard=guard,
        window_out_summary=WindowOutSummaryConfig(enabled=False),
    )
    history_svc = HistoryContextService(cfg, _calc(limit=500))
    history_svc.compress_history_tool_results = lambda h: h  # type: ignore[method-assign]
    history_svc.split_by_remaining_budget = lambda h, b: (h, [])  # type: ignore[method-assign]

    call_keep_recents: list[int | None] = []

    def _fake_compress(
        self: ChatSessionAgent,
        base: list[dict[str, Any]],
        threshold: int,
        *,
        keep_recent: int | None = None,
    ) -> int:
        call_keep_recents.append(keep_recent)
        # First pass (default keep_recent) still over; second (0) under.
        if keep_recent == 0:
            return threshold
        return threshold + 1

    monkeypatch.setattr(
        ChatSessionAgent, "_size_aware_compress_tool_rounds", _fake_compress
    )
    monkeypatch.setattr(
        TokenCalculator,
        "count_messages_tokens",
        lambda self, messages: 10_000,
    )
    monkeypatch.setattr(
        TokenCalculator,
        "count_message_tokens",
        lambda self, message: 100,
    )

    agent = ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(limit=500, max_out=100),
        mcp_manager=MagicMock(),
        history_context_service=history_svc,
        chat_context_config=cfg,
    )
    agent._system_prompt = "sys"
    agent._working_history = []
    agent._user_message_content = "hi"
    agent._user_message_text = "hi"
    agent._window_out_summary = None
    agent._kb_context_blocks = None
    agent._user_memories = []
    agent._attachment_uploads = None
    base = agent._compose_messages("sys", [], "hi", [])
    action, _ = await agent.unified_context_guard(
        base_prompt_messages=base,
        conversation_id="conv",
        allow_stop_tools=True,
    )
    assert action == "ok"
    assert call_keep_recents == [None, 0]


@pytest.mark.asyncio
async def test_unified_context_guard_disabled_skips() -> None:
    cfg = ChatContextConfig(
        unified_guard=UnifiedContextGuardConfig(enabled=False),
    )
    agent = ChatSessionAgent(
        think_mode=False,
        llm_config=_llm(),
        mcp_manager=MagicMock(),
        history_context_service=HistoryContextService(cfg, _calc()),
        chat_context_config=cfg,
    )
    base = [{"role": "user", "content": "hi"}]
    action, out = await agent.unified_context_guard(
        base_prompt_messages=base,
        conversation_id="c",
        allow_stop_tools=True,
    )
    assert action == "ok"
    assert out is base

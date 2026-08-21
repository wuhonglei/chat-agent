"""Tests for ToolCallPolicy.collect_iteration_hints / queue-drain."""

from __future__ import annotations

from app.agents.tool_call_policy import ToolCallPolicy
from app.mcp.constants import WEB_SEARCH_LLM
from app.schemas.llm import ToolResultMessage


def test_collect_iteration_hints_none_on_iteration_zero() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q"]},
        "c1",
        True,
    )
    assert policy.collect_iteration_hints(0) is None


def test_collect_iteration_hints_after_web_search() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q"]},
        "c1",
        True,
    )
    text = policy.collect_iteration_hints(1)
    assert text is not None
    assert "已执行过搜索" in text


def test_collect_iteration_hints_does_not_mutate_messages() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q"]},
        "c1",
        True,
    )
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "original user"},
    ]
    _ = policy.collect_iteration_hints(1)
    assert messages[-1]["content"] == "original user"


def test_collect_iteration_hints_max_search_stop() -> None:
    policy = ToolCallPolicy([])
    for i in range(2):
        policy.record_tool_arguments(
            WEB_SEARCH_LLM,
            {"queries": [f"q{i}"]},
            f"c{i}",
            True,
        )
    text = policy.collect_iteration_hints(1)
    assert text is not None
    assert "已执行 2 次搜索" in text
    assert "结果可能已足够" in text


def test_tool_round_with_empty_result_still_tracks() -> None:
    policy = ToolCallPolicy(
        [
            ToolResultMessage(
                role="tool",
                tool_call_id="c1",
                is_error=False,
                content="ok",
            )
        ]
    )
    assert policy.collect_iteration_hints(0) is None


def test_queue_after_tools_then_drain() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q"]},
        "c1",
        True,
    )
    # 第 0 轮工具结束后，按即将到来的第 1 轮入队
    policy.queue_iteration_hints_after_tools(next_iteration=1)
    text = policy.drain_pending_iteration_hints()
    assert text is not None
    assert "已执行过搜索" in text
    assert policy.drain_pending_iteration_hints() is None


def test_queue_overwrites_previous_pending() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q0"]},
        "c0",
        True,
    )
    policy.queue_iteration_hints_after_tools(next_iteration=1)
    first = policy.drain_pending_iteration_hints()
    assert first is not None

    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q1"]},
        "c1",
        True,
    )
    policy.queue_iteration_hints_after_tools(next_iteration=2)
    second = policy.drain_pending_iteration_hints()
    assert second is not None
    assert "已执行 2 次搜索" in second
    # 不应再残留 first
    assert policy.drain_pending_iteration_hints() is None


def test_reset_clears_pending_hints() -> None:
    policy = ToolCallPolicy([])
    policy.record_tool_arguments(
        WEB_SEARCH_LLM,
        {"queries": ["q"]},
        "c1",
        True,
    )
    policy.queue_iteration_hints_after_tools(next_iteration=1)
    policy.reset_for_request()
    assert policy.drain_pending_iteration_hints() is None

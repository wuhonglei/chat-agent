"""rule_evaluator 单元测试（不依赖真实 Langfuse / MCP）。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.evaluators import rule_evaluator
from app.evaluators.rule_evaluator import build_tool_whitelist, evaluate_and_score
from app.mcp.tool_naming import ToolRoute
from app.schemas.chat import AssistantResponse, TextBlock, ToolUseBlock


class _FakeSpan:
    def __init__(self) -> None:
        self.scores: list[dict[str, Any]] = []
        self.metadata_updates: list[dict[str, Any]] = []

    def score(self, **kwargs: Any) -> None:
        self.scores.append(kwargs)

    def update(self, **kwargs: Any) -> None:
        meta = kwargs.get("metadata")
        if isinstance(meta, dict):
            self.metadata_updates.append(meta)


def _score_by_name(span: _FakeSpan) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in span.scores}


def _tool_block(name: str | None, *, block_id: str = "cb_1") -> ToolUseBlock:
    if not name:
        return ToolUseBlock(id=block_id, name=None)
    # name-only is allowed for unknown/stale tools
    return ToolUseBlock(id=block_id, name=name)


def _tools_map() -> dict[str, ToolRoute]:
    return {
        "tavily_web_search": ToolRoute("tavily", "web_search"),
        "time_get_current_time": ToolRoute("time", "get_current_time"),
        "shell_exec": ToolRoute("shell", "exec"),
        "file_read_file": ToolRoute("file", "read_file"),
    }


@pytest.fixture
def mode_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_settings = MagicMock()
    fake_settings.mcp.normal_mode_servers = ["tavily", "time"]
    fake_settings.mcp.agent_mode_servers = ["shell", "file", "tavily"]
    monkeypatch.setattr(rule_evaluator, "settings", fake_settings)


def test_build_tool_whitelist_normal_mode(mode_servers: None) -> None:
    whitelist = build_tool_whitelist(0, _tools_map())
    assert whitelist == {"tavily_web_search", "time_get_current_time"}


def test_build_tool_whitelist_agent_mode(mode_servers: None) -> None:
    whitelist = build_tool_whitelist(1, _tools_map())
    assert whitelist == {
        "tavily_web_search",
        "shell_exec",
        "file_read_file",
    }


def test_valid_answer_true_for_non_empty(mode_servers: None) -> None:
    span = _FakeSpan()
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="你好",
            content_blocks=[TextBlock(id="t1", text="你好")],
        ),
        agent_mode=0,
        tool_whitelist=set(),
    )
    assert _score_by_name(span)["valid_answer"]["value"] is True
    assert span.metadata_updates and span.metadata_updates[0]["called_tools"] == []


def test_valid_answer_false_for_blank(mode_servers: None) -> None:
    span = _FakeSpan()
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="  \n\t",
            content_blocks=[TextBlock(id="t1", text="  \n\t")],
        ),
        agent_mode=0,
        tool_whitelist=set(),
    )
    assert _score_by_name(span)["valid_answer"]["value"] is False


def test_tool_whitelist_ok_when_called_in_whitelist(mode_servers: None) -> None:
    span = _FakeSpan()
    whitelist = build_tool_whitelist(0, _tools_map())
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="ok",
            content_blocks=[_tool_block("tavily_web_search")],
        ),
        agent_mode=0,
        tool_whitelist=whitelist,
    )
    scores = _score_by_name(span)
    assert scores["tool_whitelist_ok"]["value"] is True
    assert scores["tool_call_count"]["value"] == 1
    assert scores["tool_call_count"]["data_type"] == "NUMERIC"


def test_tool_whitelist_fail_mode0_agent_only_tool(mode_servers: None) -> None:
    span = _FakeSpan()
    whitelist = build_tool_whitelist(0, _tools_map())
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="ok",
            content_blocks=[_tool_block("shell_exec")],
        ),
        agent_mode=0,
        tool_whitelist=whitelist,
    )
    score = _score_by_name(span)["tool_whitelist_ok"]
    assert score["value"] is False
    assert "shell_exec" in (score.get("comment") or "")


def test_tool_whitelist_fail_mode_agent_out_of_whitelist(
    mode_servers: None,
) -> None:
    span = _FakeSpan()
    whitelist = build_tool_whitelist(1, _tools_map())
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="ok",
            content_blocks=[_tool_block("time_get_current_time")],
        ),
        agent_mode=1,
        tool_whitelist=whitelist,
    )
    assert _score_by_name(span)["tool_whitelist_ok"]["value"] is False


def test_tool_whitelist_fail_unnamed_tool(mode_servers: None) -> None:
    span = _FakeSpan()
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="ok",
            content_blocks=[_tool_block(None)],
        ),
        agent_mode=0,
        tool_whitelist={"tavily_web_search"},
    )
    assert _score_by_name(span)["tool_whitelist_ok"]["value"] is False


def test_tool_call_count_multiple_blocks(mode_servers: None) -> None:
    span = _FakeSpan()
    evaluate_and_score(
        span=span,
        assistant_response=AssistantResponse(
            content="ok",
            content_blocks=[
                _tool_block("tavily_web_search", block_id="cb_1"),
                _tool_block("time_get_current_time", block_id="cb_2"),
                _tool_block("tavily_web_search", block_id="cb_3"),
            ],
        ),
        agent_mode=0,
        tool_whitelist={"tavily_web_search", "time_get_current_time"},
    )
    assert _score_by_name(span)["tool_call_count"]["value"] == 3


def test_evaluate_and_score_swallows_errors(
    monkeypatch: pytest.MonkeyPatch, mode_servers: None
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("score failed")

    monkeypatch.setattr(rule_evaluator, "score_observation", _boom)
    # 不应抛异常
    evaluate_and_score(
        span=_FakeSpan(),
        assistant_response=AssistantResponse(content="ok"),
        agent_mode=0,
        tool_whitelist=set(),
    )

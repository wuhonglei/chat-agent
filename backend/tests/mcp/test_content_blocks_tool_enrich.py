"""Tests for ToolUseBlock enrich in ContentBlocksAggregator."""

from __future__ import annotations

from types import SimpleNamespace

from app.agents.utils.content_blocks import ContentBlocksAggregator
from app.mcp.tool_naming import ToolRoute


def test_process_tool_call_deltas_enriches_three_fields() -> None:
    agg = ContentBlocksAggregator()
    agg.set_tool_name_resolver(
        lambda name: ToolRoute(server_name="tavily", mcp_tool_name="web_search")
        if name == "tavily_web_search"
        else None
    )

    delta = SimpleNamespace(
        index=0,
        id="call_1",
        function=SimpleNamespace(name="tavily_web_search", arguments='{"q":'),
    )
    events = agg.process_tool_call_deltas([delta])

    block = agg.blocks[0]
    assert block.name == "tavily_web_search"
    assert block.server_name == "tavily"
    assert block.mcp_tool_name == "web_search"

    tool_delta = next(e for e in events if e.get("op") == "tool_delta")
    assert tool_delta["server_name"] == "tavily"
    assert tool_delta["mcp_tool_name"] == "web_search"


def test_process_tool_call_deltas_unknown_tool_does_not_crash() -> None:
    """未知/过时工具名不应中断流，仅保留原始名、不写路由信息。"""
    agg = ContentBlocksAggregator()
    agg.set_tool_name_resolver(lambda _name: None)

    delta = SimpleNamespace(
        index=0,
        id="call_1",
        function=SimpleNamespace(name="tavily_web_crawl", arguments='{"url":'),
    )
    events = agg.process_tool_call_deltas([delta])

    block = agg.blocks[0]
    assert block.name == "tavily_web_crawl"
    assert block.server_name is None
    assert block.mcp_tool_name is None

    tool_delta = next(e for e in events if e.get("op") == "tool_delta")
    assert tool_delta["name"] == "tavily_web_crawl"
    assert "server_name" not in tool_delta
    assert "mcp_tool_name" not in tool_delta

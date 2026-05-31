"""Tests for prefixed LLM tool names in MCPToolGateway."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.mcp.gateway import MCPToolGateway
from app.mcp.tool_naming import ToolRoute


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, description="", inputSchema={"type": "object"})


@pytest.fixture
def gateway_with_duplicate_bare_names() -> MCPToolGateway:
    registry = MagicMock()
    registry.get_servers.return_value = {"alpha", "beta"}

    pool = MagicMock()
    pool._initialized = True
    pool.tools_by_server = {
        "alpha": [_tool("search")],
        "beta": [_tool("search")],
    }
    pool.ensure_initialized = MagicMock()

    gw = MCPToolGateway(pool, registry)
    gw.rebuild_tool_index()
    return gw


def test_rebuild_tool_index_uses_prefixed_names(
    gateway_with_duplicate_bare_names: MCPToolGateway,
) -> None:
    gw = gateway_with_duplicate_bare_names
    assert gw.tools_map == {
        "alpha_search": ToolRoute(server_name="alpha", mcp_tool_name="search"),
        "beta_search": ToolRoute(server_name="beta", mcp_tool_name="search"),
    }


def test_get_tools_for_llm_exposes_prefixed_names(
    gateway_with_duplicate_bare_names: MCPToolGateway,
) -> None:
    gw = gateway_with_duplicate_bare_names
    tools = gw.get_tools_for_llm(["alpha", "beta"])
    names = {item["function"]["name"] for item in tools}
    assert names == {"alpha_search", "beta_search"}


@pytest.mark.asyncio
async def test_call_tool_strips_prefix_before_mcp(
    gateway_with_duplicate_bare_names: MCPToolGateway,
) -> None:
    gw = gateway_with_duplicate_bare_names
    client = MagicMock()
    enter = AsyncMock(return_value=client)
    exit = AsyncMock(return_value=None)
    client.__aenter__ = enter
    client.__aexit__ = exit
    client.call_tool = AsyncMock(return_value="ok")
    gw.pool.clients = {"alpha": client}

    result, warnings = await gw.call_tool("alpha_search", {"q": "test"})
    assert result == "ok"
    assert warnings == []
    client.call_tool.assert_awaited_once()
    args, _kwargs = client.call_tool.call_args
    assert args[0] == "search"
    assert args[1] == {"q": "test"}


@pytest.mark.asyncio
async def test_call_tool_rejects_bare_name(
    gateway_with_duplicate_bare_names: MCPToolGateway,
) -> None:
    gw = gateway_with_duplicate_bare_names
    with pytest.raises(ValueError, match="不存在"):
        await gw.call_tool("search", {})


@pytest.mark.asyncio
async def test_call_tool_accepts_prefixed_skill_manager_name() -> None:
    registry = MagicMock()
    registry.get_servers.return_value = {"skill_manager"}

    pool = MagicMock()
    pool._initialized = True
    pool.tools_by_server = {"skill_manager": [_tool("load_skill")]}
    pool.ensure_initialized = MagicMock()

    gw = MCPToolGateway(pool, registry)
    gw.rebuild_tool_index()

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.call_tool = AsyncMock(return_value="ok")
    gw.pool.clients = {"skill_manager": client}

    result, warnings = await gw.call_tool("skill_manager_load_skill", {"name": "demo"})
    assert result == "ok"
    assert warnings == []
    client.call_tool.assert_awaited_once()
    args, _kwargs = client.call_tool.call_args
    assert args[0] == "load_skill"

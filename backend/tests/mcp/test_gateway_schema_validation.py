"""Tests for MCPToolGateway JSON Schema argument validation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.mcp.errors import ToolArgumentValidationError
from app.mcp.gateway import MCPToolGateway


def _tool(name: str, schema: dict | None) -> SimpleNamespace:
    return SimpleNamespace(name=name, description="", inputSchema=schema)


def _gateway_with_tool(
    *,
    schema: dict | None,
    tool_name: str = "demo",
    server_name: str = "alpha",
) -> tuple[MCPToolGateway, MagicMock]:
    registry = MagicMock()
    registry.get_servers.return_value = {server_name}

    pool = MagicMock()
    pool._initialized = True
    pool.tools_by_server = {server_name: [_tool(tool_name, schema)]}
    pool.ensure_initialized = MagicMock()

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.call_tool = AsyncMock(return_value="ok")
    pool.clients = {server_name: client}

    gw = MCPToolGateway(pool, registry)
    gw.rebuild_tool_index()
    return gw, client


@pytest.mark.asyncio
async def test_call_tool_rejects_wrong_type() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"count": {"type": "integer"}},
        "required": ["count"],
    }
    gw, client = _gateway_with_tool(schema=schema)

    with pytest.raises(ToolArgumentValidationError, match="参数校验失败"):
        await gw.call_tool("alpha_demo", {"count": "not-int"})

    client.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_tool_rejects_missing_required() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    }
    gw, client = _gateway_with_tool(schema=schema)

    with pytest.raises(ToolArgumentValidationError, match="参数校验失败"):
        await gw.call_tool("alpha_demo", {})

    client.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_tool_filters_unknown_keys_before_validate() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    }
    gw, client = _gateway_with_tool(schema=schema)

    result, warnings = await gw.call_tool(
        "alpha_demo", {"q": "ok", "extra": "ignored"}
    )
    assert result == "ok"
    assert len(warnings) == 1
    assert warnings[0]["details"]["removed_params"] == ["extra"]
    client.call_tool.assert_awaited_once()
    args, _kwargs = client.call_tool.call_args
    assert args[1] == {"q": "ok"}


@pytest.mark.asyncio
async def test_call_tool_skips_validation_when_schema_missing() -> None:
    gw, client = _gateway_with_tool(schema=None)

    result, warnings = await gw.call_tool("alpha_demo", {"any": 1})
    assert result == "ok"
    assert warnings == []
    client.call_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_tool_skips_validation_when_schema_invalid() -> None:
    # invalid: type as list without proper draft structure that still may fail
    schema = {
        "type": "object",
        "properties": {"q": {"type": ["not-a-real-type"]}},
        "required": ["q"],
    }
    gw, client = _gateway_with_tool(schema=schema)

    # SchemaError path skips validation; call proceeds
    result, _warnings = await gw.call_tool("alpha_demo", {"q": "x"})
    assert result == "ok"
    client.call_tool.assert_awaited_once()

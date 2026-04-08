"""Facade for MCP registry, connection pool, and tool gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.mcp.mcp_connection_pool import MCPConnectionPool
from app.mcp.mcp_registry import MCPRegistry
from app.mcp.mcp_tool_gateway import MCPToolGateway
from app.schemas.mcp import MCPConfigForFeDict


class MCPClientManager:
    """Backwards-compatible facade for MCP infrastructure components."""

    def __init__(self) -> None:
        self.registry = MCPRegistry()
        self.pool = MCPConnectionPool(self.registry)
        self.gateway = MCPToolGateway(self.pool, self.registry)

    @property
    def clients(self) -> dict[str, Any]:
        return self.pool.clients

    @property
    def tools_by_server(self) -> dict[str, list[Any]]:
        return self.pool.tools_by_server

    @property
    def tools_map(self) -> dict[str, str]:
        return self.gateway.tools_map

    @property
    def _initialized(self) -> bool:
        return self.pool._initialized

    async def initialize(self) -> None:
        await self.pool.initialize()
        self.gateway.rebuild_tool_index()

    def cleanup(self) -> None:
        self.gateway.tools_map.clear()
        self.pool.cleanup()

    async def list_tools(
        self, server_names: list[str] | None = None
    ) -> dict[str, list[Any]]:
        return await self.pool.list_tools(server_names)

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any, list[str]]:
        return await self.gateway.call_tool(tool_name, arguments)

    @staticmethod
    def format_mcp_result(result: Any) -> str:
        return MCPToolGateway.format_mcp_result(result)

    async def get_tool_info(self, tool_name: str) -> Any | None:
        return await self.gateway.get_tool_info(tool_name)

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self.gateway.get_server_for_tool(tool_name)

    @asynccontextmanager
    async def managed_session(self) -> AsyncIterator[MCPClientManager]:
        try:
            await self.initialize()
            yield self
        finally:
            self.cleanup()

    async def health_check(self) -> dict[str, bool]:
        return await self.gateway.health_check()

    async def get_mcp_config_for_fe(self) -> list[MCPConfigForFeDict]:
        return await self.gateway.get_mcp_config_for_fe()

    async def get_tools_for_llm(
        self, server_names: list[str] | None, client_ip: str | None = None
    ) -> list[dict[str, Any]]:
        return self.gateway.get_tools_for_llm(server_names, client_ip)


mcp_client_manager = MCPClientManager()
mcp_config_for_fe = mcp_client_manager.registry.get_fe_configs()


async def get_mcp_manager() -> MCPClientManager:
    if not mcp_client_manager._initialized:
        await mcp_client_manager.initialize()
    return mcp_client_manager

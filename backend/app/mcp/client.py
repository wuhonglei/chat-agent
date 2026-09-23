"""Facade for MCP registry, connection pool, and tool gateway."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import settings
from app.mcp.connection_pool import MCPConnectionPool
from app.mcp.constants import DELEGATE_TASK_ROUTE
from app.mcp.gateway import MCPToolGateway
from app.mcp.registry import MCPRegistry
from app.mcp.tool_naming import ToolRoute
from app.utils.logger import logger


class MCPClientManager:
    """Backwards-compatible facade for MCP infrastructure components."""

    def __init__(self) -> None:
        self.registry = MCPRegistry()
        self.pool = MCPConnectionPool(self.registry)
        self.gateway = MCPToolGateway(self.pool, self.registry)
        self._reload_lock = asyncio.Lock()

    @property
    def clients(self) -> dict[str, Any]:
        return self.pool.clients

    @property
    def tools_by_server(self) -> dict[str, list[Any]]:
        return self.pool.tools_by_server

    @property
    def tools_map(self) -> dict[str, ToolRoute]:
        return self.gateway.tools_map

    @property
    def _initialized(self) -> bool:
        return self.pool._initialized

    async def initialize(self) -> None:
        await self.pool.initialize()
        self.gateway.rebuild_tool_index()
        self._validate_subagent_excluded_tools()

    async def reload_async(self) -> None:
        """Tear down connections and rebuild from current ``settings.mcp``."""
        async with self._reload_lock:
            mcp = settings.mcp
            logger.info(
                "Reloading MCP manager",
                server_names=sorted(mcp.mcp_servers),
            )
            self.gateway.tools_map.clear()
            self.pool.cleanup()
            self.registry.reload_from_config()
            await self.pool.initialize()
            self.gateway.rebuild_tool_index()
            self._validate_subagent_excluded_tools()
            logger.info(
                "MCP manager reload complete",
                active_servers=sorted(self.pool.clients),
                tool_count=len(self.gateway.tools_map),
            )

    def cleanup(self) -> None:
        self.gateway.tools_map.clear()
        self.pool.cleanup()

    async def list_tools(
        self, server_names: list[str] | None = None
    ) -> dict[str, list[Any]]:
        async with self._reload_lock:
            return await self.pool.list_tools(server_names)

    def _is_delegate_task(self, tool_name: str) -> bool:
        return self.get_tool_route(tool_name) == DELEGATE_TASK_ROUTE

    def _validate_subagent_excluded_tools(self) -> None:
        from app.services.subagent.tool_filter import validate_excluded_tools

        validate_excluded_tools(
            get_tool_route=self.get_tool_route,
            registered_servers=set(self.registry.get_servers()),
        )

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any, list[dict[str, Any]]]:
        # delegate_task 会嵌套调用其它 MCP 工具。若在整段执行期间占住 reload 锁，
        # 同批工具会一直排队，子调用也会在同一把锁上死锁。
        if self._is_delegate_task(tool_name):
            return await self.gateway.call_tool(tool_name, arguments)
        async with self._reload_lock:
            return await self.gateway.call_tool(tool_name, arguments)

    @staticmethod
    def format_mcp_result(result: Any) -> str:
        return MCPToolGateway.format_mcp_result(result)

    async def get_tool_info(self, tool_name: str) -> Any | None:
        async with self._reload_lock:
            return self.gateway.get_tool_info(tool_name)

    def get_tool_route(self, tool_name: str) -> ToolRoute | None:
        return self.gateway.get_tool_route(tool_name)

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self.gateway.get_server_for_tool(tool_name)

    @asynccontextmanager
    async def managed_session(self) -> AsyncIterator[MCPClientManager]:
        try:
            await self.initialize()
            yield self
        finally:
            self.cleanup()

    async def get_tools_for_llm(
        self, server_names: list[str] | None
    ) -> list[dict[str, Any]]:
        async with self._reload_lock:
            return self.gateway.get_tools_for_llm(server_names)

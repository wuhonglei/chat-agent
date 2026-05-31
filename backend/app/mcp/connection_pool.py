"""Connection lifecycle management for MCP clients."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.client import (
    FastMCPTransport,
    StdioTransport,
    StreamableHttpTransport,
)

from app.mcp.registry import MCPRegistry
from app.utils.logger import logger


class MCPConnectionPool:
    """Initialize clients and cache per-server tool lists."""

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry
        self.clients: dict[str, Client[Any]] = {}
        self.tools_by_server: dict[str, list[Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            logger.warning("MCPConnectionPool already initialized")
            return

        logger.info("Initializing MCP connection pool")
        servers = self.registry.get_servers()
        for server_name, server_instance in servers.items():
            try:
                transport: Any
                if isinstance(server_instance, FastMCP):
                    transport = FastMCPTransport(server_instance)
                    logger.info(
                        "Using FastMCPTransport for local server",
                        server_name=server_name,
                        transport_type="FastMCPTransport",
                    )
                elif isinstance(server_instance, dict) and "url" in server_instance:
                    transport = StreamableHttpTransport(
                        url=server_instance["url"],
                        headers=server_instance.get("headers", {}),
                    )
                    logger.info(
                        "Using StreamableHttpTransport for remote server",
                        server_name=server_name,
                        transport_type="StreamableHttpTransport",
                    )
                elif isinstance(server_instance, dict) and "command" in server_instance:
                    transport = StdioTransport(**server_instance)
                    logger.info(
                        "Using StdioTransport for local server",
                        server_name=server_name,
                        transport_type="StdioTransport",
                    )
                else:
                    transport = server_instance
                    logger.info(
                        "Using custom transport for server",
                        server_name=server_name,
                        transport_type="custom",
                    )
                self.clients[server_name] = Client(
                    transport=transport, init_timeout=5.0
                )
                logger.info("MCP Server registered", server_name=server_name)
            except Exception as exc:
                logger.error(
                    "Failed to register MCP Server",
                    error=exc,
                    server_name=server_name,
                )

        for server_name, client in self.clients.items():
            try:
                async with client:
                    tools = await client.list_tools()
                    self.tools_by_server[server_name] = tools
                logger.info(
                    "MCP Server connected",
                    server_name=server_name,
                    tool_count=len(tools),
                )
            except Exception as exc:
                logger.error(
                    "Failed to connect MCP Server",
                    error=exc,
                    server_name=server_name,
                )

        self._initialized = True
        logger.info(
            "MCP connection pool initialized",
            total_servers=len(self.clients),
        )

    def cleanup(self) -> None:
        logger.info("Cleaning up MCP connection pool")
        self.clients.clear()
        self.tools_by_server.clear()
        self._initialized = False

    async def list_tools(
        self, server_names: list[str] | None = None
    ) -> dict[str, list[Any]]:
        self.ensure_initialized()
        all_tools: dict[str, list[Any]] = {}
        target_servers = (
            list(self.clients.keys()) if server_names is None else server_names
        )
        if not target_servers:
            return {}

        async def list_tools_for_server(server_name: str) -> list[Any]:
            if server_name not in self.clients:
                return []
            client = self.clients[server_name]
            async with client:
                return await client.list_tools()

        results = await asyncio.gather(
            *[list_tools_for_server(name) for name in target_servers],
            return_exceptions=True,
        )
        for server_name, tools in zip(target_servers, results):
            if isinstance(tools, BaseException):
                logger.error(
                    "Failed to get tools list",
                    error=tools
                    if isinstance(tools, Exception)
                    else Exception(str(tools)),
                    server_name=server_name,
                )
            else:
                all_tools[server_name] = tools
        return all_tools

    def ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("MCPClientManager 未初始化，请先调用 initialize()")

    @asynccontextmanager
    async def managed_session(self) -> AsyncIterator[MCPConnectionPool]:
        try:
            await self.initialize()
            yield self
        finally:
            self.cleanup()

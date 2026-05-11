"""Tool lookup, filtering, and execution for MCP clients."""

from __future__ import annotations

import copy
from typing import Any

from app.mcp.mcp_connection_pool import MCPConnectionPool
from app.mcp.mcp_registry import MCPRegistry
from app.schemas.mcp import MCPConfigForFeDict
from app.utils.logger import logger


class MCPToolGateway:
    """Resolve tool metadata and execute tools through the connection pool."""

    AGENT_SKILLS_SERVER_NAME = "agent-skills-mcp"

    def __init__(self, pool: MCPConnectionPool, registry: MCPRegistry) -> None:
        self.pool = pool
        self.registry = registry
        self.tools_map: dict[str, str] = {}

    def rebuild_tool_index(self) -> None:
        self.tools_map.clear()
        for server_name, tools in self.pool.tools_by_server.items():
            for tool in tools:
                tool_name = tool.name
                if tool_name in self.tools_map:
                    logger.warning(
                        "Tool name conflict",
                        tool_name=tool_name,
                        existing_server=self.tools_map[tool_name],
                        new_server=server_name,
                    )
                self.tools_map[tool_name] = server_name

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any, list[str]]:
        self.pool.ensure_initialized()
        if tool_name not in self.tools_map:
            available_tools = ", ".join(self.tools_map.keys())
            raise ValueError(f"工具 '{tool_name}' 不存在。可用工具: {available_tools}")

        server_name = self.tools_map[tool_name]
        client = self.pool.clients[server_name]
        filtered_arguments = self._filter_tool_arguments(
            tool_name, server_name, arguments or {}
        )
        removed_params = list(set(arguments or {}) - set(filtered_arguments))
        try:
            logger.info(
                "Calling tool",
                tool_name=tool_name,
                server_name=server_name,
            )
            if removed_params:
                logger.warning(
                    "Filtered unsupported tool arguments",
                    tool_name=tool_name,
                    removed_params=removed_params,
                )
            async with client:
                result = await client.call_tool(
                    tool_name, filtered_arguments, timeout=60
                )
            logger.info(
                "Tool executed successfully",
                tool_name=tool_name,
                server_name=server_name,
            )
            return result, removed_params
        except Exception as exc:
            logger.error(
                "Tool execution failed",
                error=exc,
                tool_name=tool_name,
                server_name=server_name,
            )
            raise

    def _filter_tool_arguments(
        self, tool_name: str, server_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if server_name not in self.pool.tools_by_server:
            return arguments

        for tool in self.pool.tools_by_server[server_name]:
            if tool.name != tool_name:
                continue
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                properties = tool.inputSchema.get("properties", {})
                supported_params = set(properties.keys())
                return {
                    key: value
                    for key, value in arguments.items()
                    if key in supported_params
                }
        return arguments

    @staticmethod
    def format_mcp_result(result: Any) -> str:
        if hasattr(result, "content"):
            if isinstance(result.content, list):
                text_parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                return "\n".join(text_parts)
            if hasattr(result.content, "text"):
                return str(result.content.text)
            return str(result.content)
        return str(result)

    async def get_tool_info(self, tool_name: str) -> Any | None:
        self.pool.ensure_initialized()
        if tool_name not in self.tools_map:
            return None

        server_name = self.tools_map[tool_name]
        client = self.pool.clients[server_name]
        async with client:
            tools = await client.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool
        return None

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self.tools_map.get(tool_name)

    async def health_check(self) -> dict[str, bool]:
        self.pool.ensure_initialized()
        health_status: dict[str, bool] = {}
        for server_name in self.pool.clients:
            logger.info("Health check passed", server_name=server_name)
            health_status[server_name] = server_name in self.pool.tools_by_server
        return health_status

    async def get_mcp_config_for_fe(self) -> list[MCPConfigForFeDict]:
        self.pool.ensure_initialized()
        health_status = await self.health_check()
        mcp_config_for_fe_copy = copy.deepcopy(self.registry.get_fe_configs())
        for server in mcp_config_for_fe_copy:
            server["online"] = health_status.get(server["id"], False)
        return mcp_config_for_fe_copy

    def get_tools_for_llm(
        self, server_names: list[str] | None, client_ip: str | None = None
    ) -> list[dict[str, Any]]:
        self.pool.ensure_initialized()
        formatted_tools = []
        final_server_names = (
            set(self.pool.tools_by_server.keys())
            if server_names is None
            else set(server_names)
        )
        if client_ip:
            final_server_names.add("ip-locator-mcp")
        else:
            final_server_names.discard("ip-locator-mcp")

        for server_name in final_server_names:
            if server_name not in self.pool.tools_by_server:
                continue
            tools = self.pool.tools_by_server[server_name]
            for tool in tools:
                parameters = tool.inputSchema if hasattr(tool, "inputSchema") else {}
                parameters_for_llm = self._sanitize_tool_schema_for_llm(
                    server_name=server_name,
                    tool_name=tool.name,
                    parameters=parameters,
                )
                formatted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": parameters_for_llm,
                        },
                    }
                )
        return formatted_tools

    def _sanitize_tool_schema_for_llm(
        self, *, server_name: str, tool_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if server_name != self.AGENT_SKILLS_SERVER_NAME:
            return parameters
        if not parameters:
            return parameters
        sanitized = copy.deepcopy(parameters)
        properties = sanitized.get("properties")
        if isinstance(properties, dict):
            properties.pop("user_id", None)
            properties.pop("workspace_id", None)
        required = sanitized.get("required")
        if isinstance(required, list):
            sanitized["required"] = [
                item for item in required if item not in {"user_id", "workspace_id"}
            ]
        return sanitized

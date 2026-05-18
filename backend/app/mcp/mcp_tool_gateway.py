"""Tool lookup, filtering, and execution for MCP clients."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_connection_pool import MCPConnectionPool
from app.mcp.mcp_registry import MCPRegistry
from app.utils.logger import logger


class MCPToolGateway:
    """Resolve tool metadata and execute tools through the connection pool."""

    DEFAULT_TOOL_CALL_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        pool: MCPConnectionPool,
        registry: MCPRegistry,
        *,
        strict_tool_name_conflict: bool = False,
        tool_call_timeout_seconds: int = DEFAULT_TOOL_CALL_TIMEOUT_SECONDS,
        tool_call_timeout_seconds_by_server: dict[str, int] | None = None,
    ) -> None:
        self.pool = pool
        self.registry = registry
        self.tools_map: dict[str, str] = {}
        self.tool_conflicts: dict[str, list[str]] = {}
        self.strict_tool_name_conflict = strict_tool_name_conflict
        self.tool_call_timeout_seconds = tool_call_timeout_seconds
        self.tool_call_timeout_seconds_by_server = (
            dict(tool_call_timeout_seconds_by_server)
            if tool_call_timeout_seconds_by_server
            else {}
        )

    def rebuild_tool_index(self) -> None:
        self.tools_map.clear()
        self.tool_conflicts.clear()
        ordered_server_names = [
            server_name
            for server_name in self.registry.get_servers()
            if server_name in self.pool.tools_by_server
        ]
        for server_name in ordered_server_names:
            tools = self.pool.tools_by_server[server_name]
            for tool in tools:
                tool_name = tool.name
                existing_server = self.tools_map.get(tool_name)
                if existing_server and existing_server != server_name:
                    conflict_servers = self.tool_conflicts.setdefault(
                        tool_name, [existing_server]
                    )
                    if server_name not in conflict_servers:
                        conflict_servers.append(server_name)
                    logger.warning(
                        "Tool name conflict",
                        tool_name=tool_name,
                        existing_server=existing_server,
                        new_server=server_name,
                        conflict_policy=(
                            "raise"
                            if self.strict_tool_name_conflict
                            else "keep_first_server"
                        ),
                    )
                    if self.strict_tool_name_conflict:
                        raise ValueError(
                            f"Tool name conflict: '{tool_name}' is registered by "
                            f"{', '.join(conflict_servers)}"
                        )
                    continue
                self.tools_map[tool_name] = server_name

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any, list[dict[str, Any]]]:
        self.pool.ensure_initialized()
        if tool_name not in self.tools_map:
            available_tools = ", ".join(self.tools_map.keys())
            raise ValueError(f"工具 '{tool_name}' 不存在。可用工具: {available_tools}")

        server_name = self.tools_map[tool_name]
        client = self.pool.clients[server_name]
        prepared_arguments = self._prepare_tool_arguments(
            tool_name=tool_name,
            server_name=server_name,
            arguments=arguments or {},
        )
        (
            filtered_arguments,
            removed_params,
            schema_mode,
        ) = self._filter_tool_arguments(
            tool_name=tool_name,
            server_name=server_name,
            arguments=prepared_arguments,
        )
        self._validate_tool_arguments(
            tool_name=tool_name,
            server_name=server_name,
            arguments=filtered_arguments,
        )
        warnings = self._collect_warnings(
            tool_name=tool_name,
            removed_params=removed_params,
            schema_mode=schema_mode,
        )
        try:
            logger.info(
                "Calling tool",
                tool_name=tool_name,
                server_name=server_name,
                schema_mode=schema_mode,
                removed_params_count=len(removed_params),
            )
            if warnings:
                logger.warning(
                    "Prepared tool warnings",
                    tool_name=tool_name,
                    warnings=warnings,
                )
            async with client:
                result = await client.call_tool(
                    tool_name,
                    filtered_arguments,
                    timeout=self._resolve_tool_call_timeout(server_name),
                )
            logger.info(
                "Tool executed successfully",
                tool_name=tool_name,
                server_name=server_name,
            )
            return result, warnings
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
    ) -> tuple[dict[str, Any], list[str], str]:
        schema = self._get_tool_input_schema(
            tool_name=tool_name, server_name=server_name
        )
        if not schema:
            return arguments, [], "schema_missing"
        if not self._should_apply_strict_schema_filter(schema):
            return arguments, [], "passthrough"
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return arguments, [], "passthrough"
        supported_params = set(properties.keys())
        filtered_arguments = {
            key: value for key, value in arguments.items() if key in supported_params
        }
        removed_params = sorted(set(arguments) - set(filtered_arguments))
        return filtered_arguments, removed_params, "strict_whitelist"

    @staticmethod
    def _should_apply_strict_schema_filter(schema: dict[str, Any]) -> bool:
        if schema.get("type") != "object":
            return False
        if schema.get("additionalProperties") is not False:
            return False
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return False
        has_composition = any(
            key in schema for key in ("oneOf", "allOf", "anyOf", "$ref")
        )
        return not has_composition

    def _prepare_tool_arguments(
        self, *, tool_name: str, server_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        _ = (tool_name, server_name)
        return dict(arguments)

    def _validate_tool_arguments(
        self, *, tool_name: str, server_name: str, arguments: dict[str, Any]
    ) -> None:
        schema = self._get_tool_input_schema(
            tool_name=tool_name, server_name=server_name
        )
        if not schema:
            return
        required = schema.get("required")
        if not isinstance(required, list):
            return
        required_fields = [item for item in required if isinstance(item, str)]
        missing_required = sorted(
            field for field in required_fields if field not in arguments
        )
        if missing_required:
            raise ValueError(
                f"工具 '{tool_name}' 缺少必填参数: {', '.join(missing_required)}"
            )

    @staticmethod
    def _collect_warnings(
        *, tool_name: str, removed_params: list[str], schema_mode: str
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        if removed_params:
            warnings.append(
                {
                    "code": "unsupported_arguments_filtered",
                    "message": (
                        f"工具 {tool_name} 不支持以下参数，已在调用前忽略: "
                        f"{', '.join(removed_params)}"
                    ),
                    "details": {
                        "tool_name": tool_name,
                        "removed_params": removed_params,
                        "schema_mode": schema_mode,
                    },
                }
            )
        return warnings

    def _get_tool_input_schema(
        self, *, tool_name: str, server_name: str
    ) -> dict[str, Any] | None:
        if server_name not in self.pool.tools_by_server:
            return None
        for tool in self.pool.tools_by_server[server_name]:
            if tool.name != tool_name:
                continue
            schema = getattr(tool, "inputSchema", None)
            if isinstance(schema, dict):
                return schema
            return None
        return None

    def _resolve_tool_call_timeout(self, server_name: str) -> int:
        timeout = self.tool_call_timeout_seconds_by_server.get(
            server_name, self.tool_call_timeout_seconds
        )
        return timeout if timeout > 0 else self.DEFAULT_TOOL_CALL_TIMEOUT_SECONDS

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

    def get_tools_for_llm(self, server_names: list[str] | None) -> list[dict[str, Any]]:
        self.pool.ensure_initialized()
        formatted_tools = []
        if server_names is None:
            final_server_names = [
                server_name
                for server_name in self.registry.get_servers()
                if server_name in self.pool.tools_by_server
            ]
        else:
            final_server_names = [
                server_name
                for server_name in dict.fromkeys(server_names)
                if server_name in self.pool.tools_by_server
            ]
        for server_name in final_server_names:
            tools = self.pool.tools_by_server[server_name]
            for tool in tools:
                parameters = tool.inputSchema if hasattr(tool, "inputSchema") else {}
                formatted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": parameters,
                        },
                    }
                )
        return formatted_tools

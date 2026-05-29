"""Tool lookup, filtering, and execution for MCP clients."""

from __future__ import annotations

from typing import Any

from app.mcp.connection_pool import MCPConnectionPool
from app.mcp.registry import MCPRegistry
from app.schemas.config import MCPGatewayConfig
from app.utils.logger import logger

_SCHEMA_COMPOSITION_KEYS = frozenset(("oneOf", "allOf", "anyOf", "$ref"))


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

    def apply_config(self, gateway_config: MCPGatewayConfig) -> None:
        """Apply gateway settings from ``settings.mcp.gateway`` without reconnecting."""
        self.strict_tool_name_conflict = gateway_config.strict_tool_name_conflict
        self.tool_call_timeout_seconds = gateway_config.call_tool_timeout_seconds
        self.tool_call_timeout_seconds_by_server = dict(
            gateway_config.call_tool_timeout_seconds_by_server
        )

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def rebuild_tool_index(self) -> None:
        self.tools_map.clear()
        self.tool_conflicts.clear()
        for server_name in self.registry.get_servers():
            if server_name not in self.pool.tools_by_server:
                continue
            for tool in self.pool.tools_by_server[server_name]:
                tool_name = tool.name
                existing = self.tools_map.get(tool_name)
                if existing and existing != server_name:
                    self._handle_conflict(tool_name, existing, server_name)
                    continue
                self.tools_map[tool_name] = server_name

    def _handle_conflict(self, tool_name: str, existing: str, new_server: str) -> None:
        conflicts = self.tool_conflicts.setdefault(tool_name, [existing])
        if new_server not in conflicts:
            conflicts.append(new_server)
        logger.warning(
            "Tool name conflict",
            tool_name=tool_name,
            existing_server=existing,
            new_server=new_server,
            conflict_policy="raise"
            if self.strict_tool_name_conflict
            else "keep_first_server",
        )
        if self.strict_tool_name_conflict:
            raise ValueError(
                f"Tool name conflict: '{tool_name}' is registered by "
                f"{', '.join(conflicts)}"
            )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any, list[dict[str, Any]]]:
        self.pool.ensure_initialized()
        if tool_name not in self.tools_map:
            raise ValueError(
                f"工具 '{tool_name}' 不存在。可用工具: {', '.join(self.tools_map)}"
            )

        server_name = self.tools_map[tool_name]
        client = self.pool.clients[server_name]
        args = dict(arguments or {})
        schema = self._get_tool_input_schema(tool_name, server_name)

        args, removed, mode = self._filter_arguments(args, schema)
        self._validate_required(tool_name, args, schema)
        warnings = self._build_warnings(tool_name, removed, mode)

        timeout = self._resolve_timeout(server_name)
        logger.info(
            "Calling tool",
            tool_name=tool_name,
            server_name=server_name,
            schema_mode=mode,
            removed_params_count=len(removed),
        )
        if warnings:
            logger.warning("Tool warnings", tool_name=tool_name, warnings=warnings)
        try:
            async with client:
                result = await client.call_tool(tool_name, args, timeout=timeout)
            logger.info("Tool executed", tool_name=tool_name, server_name=server_name)
            return result, warnings
        except Exception:
            logger.error("Tool failed", tool_name=tool_name, server_name=server_name)
            raise

    # ------------------------------------------------------------------
    # Argument helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_arguments(
        arguments: dict[str, Any], schema: dict[str, Any] | None
    ) -> tuple[dict[str, Any], list[str], str]:
        if not schema:
            return arguments, [], "schema_missing"
        if (
            schema.get("type") != "object"
            or schema.get("additionalProperties") is not False
        ):
            return arguments, [], "passthrough"
        if _SCHEMA_COMPOSITION_KEYS & schema.keys():
            return arguments, [], "passthrough"
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return arguments, [], "passthrough"
        allowed = set(properties)
        filtered = {k: v for k, v in arguments.items() if k in allowed}
        removed = sorted(set(arguments) - allowed)
        return filtered, removed, "strict_whitelist"

    @staticmethod
    def _validate_required(
        tool_name: str, arguments: dict[str, Any], schema: dict[str, Any] | None
    ) -> None:
        if not schema:
            return
        required = schema.get("required")
        if not isinstance(required, list):
            return
        missing = sorted(
            f for f in required if isinstance(f, str) and f not in arguments
        )
        if missing:
            raise ValueError(f"工具 '{tool_name}' 缺少必填参数: {', '.join(missing)}")

    @staticmethod
    def _build_warnings(
        tool_name: str, removed_params: list[str], schema_mode: str
    ) -> list[dict[str, Any]]:
        if not removed_params:
            return []
        return [
            {
                "code": "unsupported_arguments_filtered",
                "message": f"工具 {tool_name} 不支持以下参数，已在调用前忽略: {', '.join(removed_params)}",
                "details": {
                    "tool_name": tool_name,
                    "removed_params": removed_params,
                    "schema_mode": schema_mode,
                },
            }
        ]

    # ------------------------------------------------------------------
    # Schema & timeout
    # ------------------------------------------------------------------

    def _get_tool_input_schema(
        self, tool_name: str, server_name: str
    ) -> dict[str, Any] | None:
        tools = self.pool.tools_by_server.get(server_name)
        if not tools:
            return None
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            return None
        schema = getattr(tool, "inputSchema", None)
        return schema if isinstance(schema, dict) else None

    def _resolve_timeout(self, server_name: str) -> int:
        timeout = self.tool_call_timeout_seconds_by_server.get(
            server_name, self.tool_call_timeout_seconds
        )
        return timeout if timeout > 0 else self.DEFAULT_TOOL_CALL_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_mcp_result(result: Any) -> str:
        if not hasattr(result, "content"):
            return str(result)
        content = result.content
        if isinstance(content, list):
            parts = [
                (item.text if hasattr(item, "text") else item.get("text", ""))
                for item in content
            ]
            return "\n".join(parts)
        if hasattr(content, "text"):
            return str(content.text)
        return str(content)

    async def get_tool_info(self, tool_name: str) -> Any | None:
        self.pool.ensure_initialized()
        server_name = self.tools_map.get(tool_name)
        if not server_name:
            return None
        async with self.pool.clients[server_name]:
            tools = await self.pool.clients[server_name].list_tools()
        return next((t for t in tools if t.name == tool_name), None)

    def get_server_for_tool(self, tool_name: str) -> str | None:
        return self.tools_map.get(tool_name)

    def get_tools_for_llm(self, server_names: list[str] | None) -> list[dict[str, Any]]:
        self.pool.ensure_initialized()
        available = self.pool.tools_by_server
        if server_names is None:
            names = [s for s in self.registry.get_servers() if s in available]
        else:
            names = [s for s in dict.fromkeys(server_names) if s in available]
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": getattr(tool, "inputSchema", {}),
                },
            }
            for server_name in names
            for tool in available[server_name]
        ]

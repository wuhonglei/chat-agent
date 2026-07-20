"""Tool lookup, filtering, and execution for MCP clients."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from app.mcp.connection_pool import MCPConnectionPool
from app.mcp.errors import ToolArgumentValidationError
from app.mcp.registry import MCPRegistry
from app.mcp.tool_naming import ToolRoute, llm_tool_name
from app.utils.logger import logger

_SCHEMA_COMPOSITION_KEYS = frozenset(("oneOf", "allOf", "anyOf", "$ref"))


class MCPToolGateway:
    """Resolve tool metadata and execute tools through the connection pool."""

    TOOL_CALL_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        pool: MCPConnectionPool,
        registry: MCPRegistry,
    ) -> None:
        self.pool = pool
        self.registry = registry
        self.tools_map: dict[str, ToolRoute] = {}

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def rebuild_tool_index(self) -> None:
        self.tools_map.clear()
        for server_name in self.registry.get_servers():
            if server_name not in self.pool.tools_by_server:
                continue
            for tool in self.pool.tools_by_server[server_name]:
                llm_name = llm_tool_name(server_name, tool.name)
                self.tools_map[llm_name] = ToolRoute(
                    server_name=server_name,
                    mcp_tool_name=tool.name,
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
                f"工具 '{tool_name}' 不存在。可用工具: {', '.join(sorted(self.tools_map))}"
            )

        route = self.tools_map[tool_name]
        server_name = route.server_name
        mcp_tool_name = route.mcp_tool_name
        client = self.pool.clients[server_name]
        args = dict(arguments or {})
        schema = self._get_tool_input_schema(mcp_tool_name, server_name)

        args, removed, mode = self._filter_arguments(args, schema)
        self._validate_against_schema(tool_name, args, schema)
        warnings = self._build_warnings(tool_name, removed, mode)

        timeout = self.TOOL_CALL_TIMEOUT_SECONDS
        logger.info(
            "Calling tool",
            tool_name=tool_name,
            mcp_tool_name=mcp_tool_name,
            server_name=server_name,
            schema_mode=mode,
            removed_params_count=len(removed),
        )
        if warnings:
            logger.warning("Tool warnings", tool_name=tool_name, warnings=warnings)
        try:
            async with client:
                result = await client.call_tool(mcp_tool_name, args, timeout=timeout)
            logger.info(
                "Tool executed",
                tool_name=tool_name,
                mcp_tool_name=mcp_tool_name,
                server_name=server_name,
            )
            return result, warnings
        except Exception:
            logger.error(
                "Tool failed",
                tool_name=tool_name,
                mcp_tool_name=mcp_tool_name,
                server_name=server_name,
            )
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
    def _validate_against_schema(
        tool_name: str, arguments: dict[str, Any], schema: dict[str, Any] | None
    ) -> None:
        if not schema:
            return
        if schema.get("type") not in (None, "object"):
            return
        has_properties = isinstance(schema.get("properties"), dict)
        has_required = isinstance(schema.get("required"), list)
        if not has_properties and not has_required:
            return
        try:
            validator = Draft202012Validator(schema)
            errors = sorted(
                validator.iter_errors(arguments), key=lambda e: list(e.path)
            )
        except SchemaError as exc:
            logger.warning(
                "Skipping tool schema validation due to invalid schema",
                tool_name=tool_name,
                error=str(exc),
            )
            return
        except Exception as exc:
            logger.warning(
                "Skipping tool schema validation due to schema error",
                tool_name=tool_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return

        if not errors:
            return
        details = "; ".join(
            MCPToolGateway._format_validation_error(err) for err in errors[:5]
        )
        raise ToolArgumentValidationError(f"工具 '{tool_name}' 参数校验失败: {details}")

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        path = ".".join(str(part) for part in error.absolute_path)
        location = path or "(root)"
        return f"{location}: {error.message}"

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
    # Schema
    # ------------------------------------------------------------------

    def _get_tool(self, mcp_tool_name: str, server_name: str) -> Any | None:
        tools = self.pool.tools_by_server.get(server_name)
        if not tools:
            return None
        return next((t for t in tools if t.name == mcp_tool_name), None)

    def _get_tool_input_schema(
        self, mcp_tool_name: str, server_name: str
    ) -> dict[str, Any] | None:
        tool = self._get_tool(mcp_tool_name, server_name)
        if not tool:
            return None
        schema = getattr(tool, "inputSchema", None)
        return schema if isinstance(schema, dict) else None

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

    def get_tool_route(self, tool_name: str) -> ToolRoute | None:
        return self.tools_map.get(tool_name)

    def get_tool_info(self, tool_name: str) -> Any | None:
        self.pool.ensure_initialized()
        route = self.get_tool_route(tool_name)
        if not route:
            return None
        return self._get_tool(route.mcp_tool_name, route.server_name)

    def get_server_for_tool(self, tool_name: str) -> str | None:
        route = self.get_tool_route(tool_name)
        return route.server_name if route else None

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
                    "name": llm_tool_name(server_name, tool.name),
                    "description": tool.description or "",
                    "parameters": getattr(tool, "inputSchema", {}),
                },
            }
            for server_name in names
            for tool in available[server_name]
        ]

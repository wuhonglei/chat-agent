"""MCP package — client, registry, connection pool, gateway, and caching."""

from app.mcp._singleton import get_mcp_manager, mcp_client_manager
from app.mcp.client import MCPClientManager
from app.mcp.reload import (
    mcp_config_fingerprint,
    on_settings_reloaded,
    register_mcp_reload_target,
    schedule_mcp_reload,
)

__all__ = [
    "MCPClientManager",
    "get_mcp_manager",
    "mcp_client_manager",
    "mcp_config_fingerprint",
    "on_settings_reloaded",
    "register_mcp_reload_target",
    "schedule_mcp_reload",
]

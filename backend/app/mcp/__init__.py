"""MCP package — client, registry, connection pool, gateway, and caching."""

from app.mcp._singleton import get_mcp_client_manager, get_mcp_manager
from app.mcp.client import MCPClientManager
from app.mcp.reload import (
    mcp_config_fingerprint,
    on_settings_reloaded,
    register_mcp_reload_target,
    schedule_mcp_reload,
)

# Declared for ``__all__`` / type checkers; bound lazily via ``__getattr__``.
mcp_client_manager: MCPClientManager

__all__ = [
    "MCPClientManager",
    "get_mcp_client_manager",
    "get_mcp_manager",
    "mcp_client_manager",
    "mcp_config_fingerprint",
    "on_settings_reloaded",
    "register_mcp_reload_target",
    "schedule_mcp_reload",
]


def __getattr__(name: str) -> MCPClientManager:
    if name == "mcp_client_manager":
        return get_mcp_client_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

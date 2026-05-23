"""MCP package — client, registry, connection pool, gateway, and caching."""

from app.mcp._singleton import get_mcp_manager, mcp_client_manager
from app.mcp.client import MCPClientManager

__all__ = ["MCPClientManager", "get_mcp_manager", "mcp_client_manager"]

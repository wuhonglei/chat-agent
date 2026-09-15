"""Module-level singleton for MCPClientManager."""

from __future__ import annotations

from app.mcp.client import MCPClientManager

_mcp_client_manager: MCPClientManager | None = None


def get_mcp_client_manager() -> MCPClientManager:
    """Return the process-wide manager, creating it on first use.

    Construction is deferred so that ``import app.mcp`` (triggered by
    ``from app.mcp.tool_naming import ...`` during model import) does not
    load FastMCP servers while ``app.models.conversation_db`` is still
    initializing.
    """
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()
    return _mcp_client_manager


async def get_mcp_manager() -> MCPClientManager:
    manager = get_mcp_client_manager()
    if not manager._initialized:
        await manager.initialize()
    return manager


def __getattr__(name: str) -> MCPClientManager:
    if name == "mcp_client_manager":
        return get_mcp_client_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

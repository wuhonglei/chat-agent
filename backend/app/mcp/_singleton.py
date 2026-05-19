"""Module-level singleton for MCPClientManager."""

from __future__ import annotations

from app.mcp.client import MCPClientManager

mcp_client_manager = MCPClientManager()


async def get_mcp_manager() -> MCPClientManager:
    if not mcp_client_manager._initialized:
        await mcp_client_manager.initialize()
    return mcp_client_manager

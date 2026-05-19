"""API 层公共依赖"""

from typing import cast

from fastapi import Request

from app.mcp.client import MCPClientManager


def get_mcp_manager(request: Request) -> MCPClientManager:
    """从 app.state 获取 MCP Manager，用于依赖注入"""
    return cast(MCPClientManager, request.app.state.mcp_manager)

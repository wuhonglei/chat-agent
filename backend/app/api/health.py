"""Health check endpoints"""

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.mcp.mcp_client import MCPClientManager
from app.schemas.mcp import MCPConfigForFeDict
from app.schemas.response import ApiResponse

router = APIRouter()


def get_mcp_manager(request: Request) -> MCPClientManager:
    """获取 MCP Manager 依赖注入函数"""
    return cast(MCPClientManager, request.app.state.mcp_manager)


@router.get("")
async def health_check() -> ApiResponse[dict[str, str]]:
    """Basic health check"""
    return ApiResponse.success(data={"status": "healthy"}, msg="健康检查成功")


@router.get("/mcp")
async def mcp_health_check(
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
) -> ApiResponse[dict[str, bool]]:
    """MCP health check"""
    health_check_result = await mcp_manager.health_check()
    return ApiResponse.success(data=health_check_result, msg="MCP健康检查成功")


@router.get("/mcp_config")
async def mcp_config(
    mcp_manager: MCPClientManager = Depends(get_mcp_manager),
) -> ApiResponse[list[MCPConfigForFeDict]]:
    """Get MCP config for FE"""
    mcp_config_for_fe = await mcp_manager.get_mcp_config_for_fe()
    return ApiResponse.success(data=mcp_config_for_fe, msg="获取MCP配置成功")

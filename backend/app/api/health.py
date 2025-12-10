"""Health check endpoints"""

from typing import cast

from fastapi import APIRouter, Request

from app.models.app_state import AppState
from app.models.mcp import MCPConfigForFeDict
from app.models.response import ApiResponse
from app.utils.logger import logger


router = APIRouter()


@router.get("")
async def health_check() -> ApiResponse[dict]:
    """Basic health check"""
    return ApiResponse.success(data={"status": "healthy"}, msg="健康检查成功")


@router.get("/mcp")
async def mcp_health_check(request: Request) -> ApiResponse[dict[str, bool]]:
    """MCP health check"""
    state = cast(AppState, request.app.state)
    try:
        health_check_result = await state.mcp_manager.health_check()
        return ApiResponse.success(data=health_check_result, msg="MCP健康检查成功")
    except Exception as e:
        logger.error("MCP health check failed", error=e)
        return ApiResponse.error(code=1, msg=f"MCP健康检查失败: {str(e)}")


@router.get("/mcp_config")
async def mcp_config(request: Request) -> ApiResponse[list[MCPConfigForFeDict]]:
    """Get MCP config for FE"""
    state = cast(AppState, request.app.state)
    try:
        mcp_config_for_fe = await state.mcp_manager.get_mcp_config_for_fe()
        return ApiResponse.success(data=mcp_config_for_fe, msg="获取MCP配置成功")
    except Exception as e:
        logger.error("Get MCP config for FE failed", error=e)
        return ApiResponse.error(code=1, msg=f"获取MCP配置失败: {str(e)}")

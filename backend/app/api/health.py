"""Health check endpoints"""

from fastapi import APIRouter, Depends

from app.api.deps import get_mcp_manager
from app.mcp.mcp_client import MCPClientManager
from app.schemas.response import ApiResponse

router = APIRouter()


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

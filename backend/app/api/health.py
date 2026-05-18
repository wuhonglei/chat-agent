"""Health check endpoints"""

from fastapi import APIRouter

from app.schemas.response import ApiResponse

router = APIRouter()


@router.get("")
async def health_check() -> ApiResponse[dict[str, str]]:
    """Basic health check"""
    return ApiResponse.success(data={"status": "healthy"}, msg="健康检查成功")

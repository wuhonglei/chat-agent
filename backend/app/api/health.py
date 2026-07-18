"""Health check endpoints"""

from fastapi import APIRouter

from app.core.local_cache import l1_get, l1_set
from app.core.redis import ping_redis
from app.schemas.response import ApiResponse

router = APIRouter()


@router.get("")
async def health_check() -> ApiResponse[dict[str, str]]:
    """Basic health check"""
    redis_status = l1_get("health", "redis_ping")
    if redis_status is None:
        redis_status = "ok" if await ping_redis() else "unavailable"
        l1_set("health", "redis_ping", redis_status)
    return ApiResponse.success(
        data={"status": "healthy", "redis": redis_status},
        msg="健康检查成功",
    )

"""
用户信息
"""

from fastapi import APIRouter, Depends
from loguru import logger
from sqlmodel import Session
from app.core.db import get_db
from app.models.response import ApiResponse
from app.services.user_service import UserService
from app.utils.auth_deps import get_current_user_id

router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取用户信息"""
    logger.info("获取用户信息")

    # 获取用户信息
    user_service = UserService(db)
    user = user_service.get_user(user_id)

    return ApiResponse.success(data=user)

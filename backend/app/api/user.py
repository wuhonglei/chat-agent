"""
用户信息
"""

from fastapi import APIRouter, Depends
from loguru import logger
from app.models.response import ApiResponse
from app.models.token import SecretTokenInfo
from app.services.user_service import UserService

router = APIRouter()


@router.get("/detail")
async def get_user_detail():
    """获取用户信息"""
    logger.info("获取用户信息")
    return ApiResponse.success(data=None)
    # user_id = secret_token_info.user_id
    # with UserService() as user_service:
    #     user = user_service.get_user(user_id)
    # return ApiResponse.success(data=user)

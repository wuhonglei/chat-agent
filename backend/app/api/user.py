"""
用户信息
"""

from fastapi import APIRouter, Depends
from app.models.response import ApiResponse
from app.models.token import SecretTokenInfo
from app.utils.auth_deps import get_current_user_with_auto_refresh
from app.services.user_service import UserService

router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    secret_token_info: SecretTokenInfo = Depends(
        get_current_user_with_auto_refresh)
):
    """获取用户信息"""
    user_id = secret_token_info.user_id
    with UserService() as user_service:
        user = user_service.get_user(user_id)
    return ApiResponse.success(data=user)

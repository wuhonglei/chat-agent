"""
用户信息
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_db
from app.models.response import ApiResponse
from app.models.token import SecretTokenInfo
from app.services.user_service import UserService
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    db: Session = Depends(get_db),
    token_info: SecretTokenInfo = Depends(get_auth_token_info),
):
    """获取用户信息"""
    user_service = UserService(db)
    user = user_service.get_user(token_info.user_id)

    return ApiResponse.success(data=user)

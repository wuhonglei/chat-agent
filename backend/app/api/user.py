"""
用户信息
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.models import UserDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.schemas.user import UpdateUserInfo
from app.services.user import UserDbService
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[UserDb]:
    """获取用户信息"""
    user_service = UserDbService(db)
    user = user_service.get_user(token_info.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return ApiResponse.success(data=user)


@router.put("/update_info")
async def update_user_info(
    update_info: UpdateUserInfo,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[UserDb]:
    """更新用户信息"""
    user_service = UserDbService(db)
    user = user_service.update_user_info(token_info.user_id, update_info)
    return ApiResponse.success(data=user)

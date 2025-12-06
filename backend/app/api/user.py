"""
用户信息
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session
from fastapi import HTTPException
from app.core.db import get_db
from app.models.user import UpdateUserInfo
from app.models.response import ApiResponse
from app.models.token import SecretTokenInfo
from app.services.user_service import UserService
from app.utils.auth_deps import get_auth_token_info
from app.utils.network import get_client_ip
from loguru import logger
router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    db: Session = Depends(get_db),
    token_info: SecretTokenInfo = Depends(get_auth_token_info),
    client_ip: str | None = Depends(get_client_ip),
):
    """获取用户信息"""
    logger.info(f"Client IP: {client_ip}")
    user_service = UserService(db)
    user = user_service.get_user(token_info.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return ApiResponse.success(data=user)


@router.put("/update_info")
async def update_user_info(
    update_info: UpdateUserInfo,
    db: Session = Depends(get_db),
    token_info: SecretTokenInfo = Depends(get_auth_token_info),
):
    """更新用户信息"""
    user_service = UserService(db)
    user = user_service.update_user_info(token_info.user_id, update_info)
    return ApiResponse.success(data=user)

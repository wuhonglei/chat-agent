"""
用户信息
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.cache import invalidate_user
from app.core.config import settings
from app.core.db import get_db
from app.models import UserDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.schemas.user import (
    MemoryListResponse,
    UpdateUserInfo,
)
from app.services.user import MemoryService, UserDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.avatar import InvalidAvatarError

router = APIRouter()


@router.get("/detail")
async def get_user_detail(
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[UserDb]:
    """获取用户信息"""
    user_service = UserDbService(db)
    user = await user_service.get_or_load_user_detail(token_info.user_id)
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
    try:
        user = user_service.update_user_info(token_info.user_id, update_info)
    except InvalidAvatarError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    db.commit()
    await invalidate_user(token_info.user_id)
    return ApiResponse.success(data=user)


@router.get("/memories")
async def get_memories(
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[MemoryListResponse]:
    """查询用户记忆列表（Mem0 GET /memories 映射为新结构）"""
    memory_service = MemoryService(settings.chat_context.memory_config)
    raw_list = await memory_service.get_memories(token_info.user_id)
    return ApiResponse.success(data=MemoryListResponse(memories=raw_list))


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
) -> ApiResponse[None]:
    """删除单条用户记忆（Mem0 DELETE /memories/{memory_id}）"""
    memory_service = MemoryService(settings.chat_context.memory_config)
    try:
        await memory_service.delete_memory(memory_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"删除记忆失败: {e}") from e
    return ApiResponse.success()

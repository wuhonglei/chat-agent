"""
用户信息
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.models import UserDb
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.schemas.user import UpdateUserInfo, UserProfileItem, UserProfileList
from app.services.user import UserDbService, UserProfileItemDbService
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


@router.get("/profile_list")
async def get_user_profile_list(
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[UserProfileList]:
    """查询用户画像列表（facts、preferences）"""
    item_service = UserProfileItemDbService(db)
    facts_tuples, prefs_tuples = item_service.list_profile_items(token_info.user_id)

    def to_item(t: tuple[str, str, int, datetime]) -> UserProfileItem:
        return UserProfileItem(
            id=t[0],
            text=t[1],
            type="fact" if t[2] == 1 else "preference",
            created_at=t[3],
        )

    facts = [to_item(t) for t in facts_tuples]
    preferences = [to_item(t) for t in prefs_tuples]
    return ApiResponse.success(
        data=UserProfileList(facts=facts, preferences=preferences)
    )


@router.delete("/profile_item/{item_id}")
async def delete_user_profile_item(
    item_id: str,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[None]:
    """删除单个用户画像条目（软删除）"""
    item_service = UserProfileItemDbService(db)
    ok = item_service.soft_delete_item(token_info.user_id, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="画像条目不存在或已删除")
    return ApiResponse.success()

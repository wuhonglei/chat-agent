"""Conversations endpoints"""

import shutil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.cache import (
    invalidate_conversation,
    invalidate_conversation_list,
    invalidate_conversation_state,
)
from app.core.db import get_db
from app.schemas.auth import AuthTokenPayload
from app.schemas.conversation import (
    ConversationInfo,
    ConversationListRequest,
    ConversationListResponse,
    ConversationSearchRequest,
    ConversationSearchResponse,
    RegisterConversationRequest,
    UpdateConversationRequest,
)
from app.schemas.response import ApiResponse
from app.services.conversation import ConversationDbService
from app.utils.auth_deps import get_auth_token_info
from app.utils.cursor import InvalidCursorError
from app.utils.logger import logger
from app.vfs.paths import get_paths

router = APIRouter()


def _delete_conversation_workspace(user_id: str | None, conversation_id: str) -> None:
    """Delete the per-conversation workspace directory if it exists."""
    if not user_id:
        logger.warning(
            "Skip deleting conversation workspace because user_id is missing",
            conversation_id=conversation_id,
        )
        return

    try:
        paths = get_paths()
        safe_user_id = paths.validate_user_id(user_id)
        safe_conversation_id = paths.validate_conversation_id(conversation_id)
    except ValueError as exc:
        logger.warning(
            "Skip deleting conversation data because path id is invalid",
            conversation_id=conversation_id,
            user_id=user_id,
            error=str(exc),
        )
        return

    conversation_root = (
        get_paths().conversation_dir(safe_user_id, safe_conversation_id).resolve()
    )
    conversations_parent = get_paths().conversations_dir(safe_user_id).resolve()

    if (
        conversation_root != conversations_parent
        and conversations_parent in conversation_root.parents
    ):
        shutil.rmtree(conversation_root, ignore_errors=True)
        logger.info(
            "Conversation directory deleted",
            conversation_id=conversation_id,
            user_id=user_id,
            conversation_root=str(conversation_root),
        )


@router.post("/register")
async def register_conversation(
    request: RegisterConversationRequest,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Register a new conversation"""
    service = ConversationDbService(db)
    conversation_info = service.register_conversation(
        title=request.title, user_id=token_info.user_id, is_active=request.is_active
    )
    await invalidate_conversation_list(token_info.user_id)
    logger.info(
        "Conversation registered for chat stream",
        conversation_id=conversation_info.id,
        user_id=token_info.user_id,
    )
    return ApiResponse.success(data=conversation_info, msg="对话创建成功")


@router.get("/list")
async def get_conversations(
    request: ConversationListRequest = Depends(),
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationListResponse]:
    """游标分页获取对话列表。"""
    service = ConversationDbService(db)
    try:
        data = service.get_conversations_paginated(
            token_info.user_id, cursor=request.cursor, limit=request.limit
        )
    except InvalidCursorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse.success(data=data, msg="获取对话列表成功")


@router.get("/search")
async def search_conversations(
    request: ConversationSearchRequest = Depends(),
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationSearchResponse]:
    """按标题与消息正文搜索会话。"""
    service = ConversationDbService(db)
    try:
        data = service.search_conversations(
            token_info.user_id,
            q=request.q,
            cursor=request.cursor,
            limit=request.limit,
        )
    except InvalidCursorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse.success(data=data, msg="搜索对话成功")


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    full_content: bool = Query(False, description="返回完整的 tool_result content（eval 用）"),
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[dict[str, Any]]:
    """Get messages by conversation ID"""
    service = ConversationDbService(db)
    if not service.get_conversation(conversation_id):
        return ApiResponse.error(code=404, msg="会话不存在")

    chat_messages = service.get_messages(
        conversation_id,
        omit_tool_result_content_and_summary_when_structured=not full_content,
    )
    data = {
        "total": len(chat_messages),
        "offset": 0,
        "limit": len(chat_messages),
        "messages": chat_messages,
    }
    return ApiResponse.success(data=data, msg="获取消息列表成功")


@router.get("/detail/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Get a conversation by ID"""
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != token_info.user_id:
        return ApiResponse.error(code=404, msg="会话不存在")

    conversation_info = ConversationInfo.model_validate(
        service.conversation_to_dict(conversation)
    )
    return ApiResponse.success(data=conversation_info, msg="获取对话详情成功")


@router.put("/update/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Update a conversation by ID"""
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != token_info.user_id:
        return ApiResponse.error(code=404, msg="会话不存在")
    conversation_info = service.update_conversation(conversation, request)
    db.commit()
    await invalidate_conversation(conversation_id, token_info.user_id)
    return ApiResponse.success(data=conversation_info, msg="更新对话成功")


@router.put("/activate/{conversation_id}")
async def activate_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Activate a draft conversation."""
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != token_info.user_id:
        return ApiResponse.error(code=404, msg="会话不存在")
    conversation_info = service.activate_conversation(conversation)
    db.commit()
    await invalidate_conversation(conversation_id, token_info.user_id)
    return ApiResponse.success(data=conversation_info, msg="会话已激活")


@router.delete("/delete/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[str]:
    """Delete a conversation by ID"""
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation or conversation.user_id != token_info.user_id:
        return ApiResponse.error(code=404, msg="会话不存在")
    _delete_conversation_workspace(conversation.user_id, conversation.id)
    service.delete_conversation(conversation)
    deleted_id = conversation.id
    db.commit()
    await invalidate_conversation_state(deleted_id, token_info.user_id)
    return ApiResponse.success(data=deleted_id, msg="删除对话成功")

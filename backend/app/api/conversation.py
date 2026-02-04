"""Conversations endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_db
from app.schemas.auth import AuthTokenPayload
from app.schemas.conversation import (
    ConversationInfo,
    ConversationListRequest,
    RegisterConversationRequest,
    UpdateConversationRequest,
)
from app.schemas.response import ApiResponse
from app.services.conversation import ConversationService
from app.utils.auth_deps import get_auth_token_info, require_auth

router = APIRouter()


@router.post("/register")
async def register_conversation(
    request: RegisterConversationRequest,
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Register a new conversation"""
    service = ConversationService(db)
    conversation_info = service.register_conversation(
        title=request.title, user_id=token_info.user_id
    )
    return ApiResponse.success(data=conversation_info, msg="对话创建成功")


@router.get("/list")
async def get_conversations(
    request: ConversationListRequest = Depends(),
    db: Session = Depends(get_db),
    token_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[dict[str, Any]]:
    """分页获取对话列表。"""
    service = ConversationService(db)
    total, conversations = service.get_conversations_paginated(
        token_info.user_id, offset=request.offset, limit=request.limit
    )
    data = {
        "total": total,
        "offset": request.offset,
        "limit": request.limit,
        "conversations": conversations,
    }
    return ApiResponse.success(data=data, msg="获取对话列表成功")


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[dict[str, Any]]:
    """Get messages by conversation ID"""
    service = ConversationService(db)
    if not service.get_conversation(conversation_id):
        return ApiResponse.error(code=404, msg="会话不存在")

    chat_messages = service.get_messages(conversation_id)
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
    _auth: None = Depends(require_auth),
) -> ApiResponse[ConversationInfo]:
    """Get a conversation by ID"""
    service = ConversationService(db)
    conversation_info = service.get_conversation_info(conversation_id)
    if not conversation_info:
        return ApiResponse.error(code=404, msg="会话不存在")

    return ApiResponse.success(data=conversation_info, msg="获取对话详情成功")


@router.put("/update/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[ConversationInfo]:
    """Update a conversation by ID"""
    service = ConversationService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        return ApiResponse.error(code=404, msg="会话不存在")
    conversation_info = service.update_conversation(conversation, request)
    return ApiResponse.success(data=conversation_info, msg="更新对话成功")


@router.delete("/delete/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """Delete a conversation by ID"""
    service = ConversationService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        return ApiResponse.error(code=404, msg="会话不存在")
    service.delete_conversation(conversation)
    return ApiResponse.success(data=conversation.id, msg="删除对话成功")

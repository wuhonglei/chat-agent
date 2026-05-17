"""Conversations endpoints"""

import shutil
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_db
from app.mcp.mcp_servers.agent_skills_mcp.config import USER_DATA_ROOT
from app.mcp.mcp_servers.agent_skills_mcp.utils import (
    validate_user_id,
    validate_workspace_id,
)
from app.schemas.auth import AuthTokenPayload
from app.schemas.conversation import (
    ConversationInfo,
    ConversationListRequest,
    RegisterConversationRequest,
    UpdateConversationRequest,
)
from app.schemas.response import ApiResponse
from app.services.conversation import ConversationDbService
from app.utils.auth_deps import get_auth_token_info, require_auth
from app.utils.logger import logger

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
        safe_user_id = validate_user_id(user_id)
        safe_workspace_id = validate_workspace_id(conversation_id)
    except ValueError as exc:
        logger.warning(
            "Skip deleting conversation workspace because path id is invalid",
            conversation_id=conversation_id,
            user_id=user_id,
            error=str(exc),
        )
        return

    workspace_root = (
        USER_DATA_ROOT / safe_user_id / "workspaces" / safe_workspace_id
    ).resolve()
    user_workspaces_root = (USER_DATA_ROOT / safe_user_id / "workspaces").resolve()
    if (
        workspace_root != user_workspaces_root
        and user_workspaces_root in workspace_root.parents
    ):
        shutil.rmtree(workspace_root, ignore_errors=True)
        logger.info(
            "Conversation workspace deleted",
            conversation_id=conversation_id,
            user_id=user_id,
            workspace_root=str(workspace_root),
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
) -> ApiResponse[dict[str, Any]]:
    """分页获取对话列表。"""
    service = ConversationDbService(db)
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
    service = ConversationDbService(db)
    if not service.get_conversation(conversation_id):
        return ApiResponse.error(code=404, msg="会话不存在")

    chat_messages = service.get_messages(
        conversation_id,
        omit_tool_result_content_and_summary_when_structured=True,
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
    _auth: None = Depends(require_auth),
) -> ApiResponse[ConversationInfo]:
    """Get a conversation by ID"""
    service = ConversationDbService(db)
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
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        return ApiResponse.error(code=404, msg="会话不存在")
    conversation_info = service.update_conversation(conversation, request)
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
    return ApiResponse.success(data=conversation_info, msg="会话已激活")


@router.delete("/delete/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """Delete a conversation by ID"""
    service = ConversationDbService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        return ApiResponse.error(code=404, msg="会话不存在")
    _delete_conversation_workspace(conversation.user_id, conversation.id)
    service.delete_conversation(conversation)
    return ApiResponse.success(data=conversation.id, msg="删除对话成功")

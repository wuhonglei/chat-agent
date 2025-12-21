"""Conversations endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_db
from app.models.chat import ChatMessageItem
from app.models.conversation import (
    ConversationInfo,
    CreatedBy,
    RegisterConversationRequest,
    UpdateConversationRequest,
)
from app.models.db import ConversationDb, MessageDb
from app.models.response import ApiResponse
from app.models.token import SecretTokenInfo
from app.utils.auth_deps import get_auth_token_info, require_auth
from app.utils.date import get_datetime_now
from app.utils.logger import logger

router = APIRouter()


def conversation_to_dict(conversation: ConversationDb) -> dict:
    """Convert SQLModel Conversation instance to dict for ConversationInfo

    使用 mode="json" 自动将日期时间字段转换为 ISO 格式字符串
    """
    return conversation.model_dump(
        mode="json"
    )


@router.post("/register")
async def register_conversation(
    request: RegisterConversationRequest,
    db: Session = Depends(get_db),
    token_info: SecretTokenInfo = Depends(get_auth_token_info),
) -> ApiResponse[ConversationInfo]:
    """Register a new conversation"""
    conversation = ConversationDb(
        title=request.title, created_by=CreatedBy.DEFAULT, user_id=token_info.user_id
    )
    db.add(conversation)
    # 所有字段（id, created_at, updated_at 等）都通过 default_factory 在对象创建时生成
    # 不需要 refresh()，事务由 get_db() 自动提交
    logger.debug("Conversation registered", conversation_id=conversation.id)
    conversation_info = ConversationInfo.model_validate(
        conversation_to_dict(conversation)
    )
    return ApiResponse.success(data=conversation_info, msg="对话创建成功")


@router.get("/list")
async def get_conversations(
    db: Session = Depends(get_db),
    token_info: SecretTokenInfo = Depends(get_auth_token_info),
) -> ApiResponse[dict]:
    """Get all conversations"""
    conversations = db.exec(
        select(ConversationDb)
        .where(ConversationDb.user_id == token_info.user_id)
        .order_by(ConversationDb.last_message_created_at.desc())
    ).all()
    logger.debug("Found conversations", count=len(conversations))
    conversation_list = [
        ConversationInfo.model_validate(conversation_to_dict(conv))
        for conv in conversations
    ]
    data = {
        "total": len(conversations),
        "offset": 0,
        "limit": len(conversations),
        "conversations": conversation_list,
    }
    return ApiResponse.success(data=data, msg="获取对话列表成功")


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[dict]:
    """Get messages by conversation ID"""
    from fastapi import HTTPException

    conversation = db.get(ConversationDb, conversation_id)
    if not conversation:
        logger.error("Conversation not found", conversation_id=conversation_id)
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = db.exec(
        select(MessageDb)
        .where(MessageDb.conversation_id == conversation_id)
        .order_by(MessageDb.created_at.asc())
    ).all()
    chat_messages = [
        ChatMessageItem.model_validate(message.model_dump(mode="json"))
        for message in messages
    ]
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
    from fastapi import HTTPException

    conversation = db.get(ConversationDb, conversation_id)
    if not conversation:
        logger.error("Conversation not found", conversation_id=conversation_id)
        raise HTTPException(status_code=404, detail="对话不存在")

    logger.debug("Found conversation", conversation_id=conversation_id)
    conversation_info = ConversationInfo.model_validate(
        conversation_to_dict(conversation)
    )
    return ApiResponse.success(data=conversation_info, msg="获取对话详情成功")


@router.put("/update/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[ConversationInfo]:
    """Update a conversation by ID"""
    from fastapi import HTTPException

    conversation = db.get(ConversationDb, conversation_id)
    if not conversation:
        logger.error("Conversation not found", conversation_id=conversation_id)
        raise HTTPException(status_code=404, detail="对话不存在")

    conversation.title = request.title
    conversation.created_by = request.created_by
    conversation.updated_at = get_datetime_now()
    # updated_at 已在代码中手动设置，不需要 refresh()
    # 事务由 get_db() 自动提交
    return ApiResponse.success(
        data=conversation_to_dict(conversation), msg="更新对话成功"
    )


@router.delete("/delete/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_auth),
) -> ApiResponse[str]:
    """Delete a conversation by ID"""
    from fastapi import HTTPException

    conversation = db.get(ConversationDb, conversation_id)
    if not conversation:
        logger.error("Conversation not found", conversation_id=conversation_id)
        raise HTTPException(status_code=404, detail="对话不存在")

    db.delete(conversation)
    # 事务由 get_db() 自动提交
    return ApiResponse.success(data=conversation_id, msg="删除对话成功")

"""Conversations endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from app.models.conversation import ConversationInfo, RegisterConversationRequest
from app.models.db import Conversation
from app.core.db import get_db
from sqlmodel import Session, select
from loguru import logger

router = APIRouter()


def conversation_to_dict(conversation: Conversation) -> dict:
    """Convert SQLModel Conversation instance to dict for ConversationInfo

    使用 mode="json" 自动将日期时间字段转换为 ISO 格式字符串
    """
    return conversation.model_dump(
        mode="json",
        include={"id", "title", "created_at", "updated_at", "message_count"}
    )


@router.post("/register")
async def register_conversation(conversation: RegisterConversationRequest, db: Session = Depends(get_db)) -> ConversationInfo:
    """Register a new conversation"""
    conversation = Conversation(title=conversation.title or "新对话")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    logger.info(f"Registered conversation {conversation.id}")
    logger.info(conversation)
    return ConversationInfo.model_validate(conversation_to_dict(conversation))


@router.get("/list")
async def get_conversations(db: Session = Depends(get_db)) -> list[ConversationInfo]:
    """Get all conversations"""
    conversations = db.exec(select(Conversation).order_by(
        Conversation.updated_at.desc())).all()
    logger.info(f"Found {len(conversations)} conversations")
    return [ConversationInfo.model_validate(conversation_to_dict(conv)) for conv in conversations]


@router.get("/detail/{conversation_id}")
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ConversationInfo:
    """Get a conversation by ID"""
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        logger.error(f"Conversation {conversation_id} not found")
        raise HTTPException(
            status_code=404, detail="Conversation not found") from None
    logger.info(f"Found conversation {conversation_id}")
    return ConversationInfo.model_validate(conversation_to_dict(conversation))

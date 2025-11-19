"""Conversations endpoints"""

from fastapi import APIRouter, Depends
from app.models.chat import ChatMessageItem
from app.models.conversation import ConversationInfo, RegisterConversationRequest, UpdateConversationRequest, CreatedBy
from app.models.response import ApiResponse
from app.models.db import ConversationDb, MessageDb
from app.core.db import get_db
from sqlmodel import Session, select
from loguru import logger
from app.utils.common import get_datetime_now

router = APIRouter()


def conversation_to_dict(conversation: ConversationDb) -> dict:
    """Convert SQLModel Conversation instance to dict for ConversationInfo

    使用 mode="json" 自动将日期时间字段转换为 ISO 格式字符串
    """
    return conversation.model_dump(
        mode="json"
    )


@router.post("/register")
async def register_conversation(request: RegisterConversationRequest, db: Session = Depends(get_db)) -> ApiResponse[ConversationInfo]:
    """Register a new conversation"""
    try:
        conversation = ConversationDb(
            title=request.title, created_by=CreatedBy.DEFAULT)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.debug(f"Registered conversation {conversation.id}")
        conversation_info = ConversationInfo.model_validate(
            conversation_to_dict(conversation))
        return ApiResponse.success(data=conversation_info, msg="对话创建成功")
    except Exception as e:
        logger.error(f"Failed to register conversation: {e}")
        return ApiResponse.error(code=1, msg=f"创建对话失败: {str(e)}")


@router.get("/list")
async def get_conversations(db: Session = Depends(get_db)):
    """Get all conversations"""
    try:
        conversations = db.exec(select(ConversationDb).order_by(
            ConversationDb.last_message_created_at.desc())).all()
        logger.debug(f"Found {len(conversations)} conversations")
        conversation_list = [ConversationInfo.model_validate(
            conversation_to_dict(conv)) for conv in conversations]
        data = {
            "total": len(conversations),
            "offset": 0,
            "limit": len(conversations),
            "conversations": conversation_list
        }
        return ApiResponse.success(data=data, msg="获取对话列表成功")
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        return ApiResponse.error(code=1, msg=f"获取对话列表失败: {str(e)}")


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    """Get messages by conversation ID"""
    try:
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return ApiResponse.error(code=404, msg="对话不存在", data=None)

        messages = db.exec(select(MessageDb).where(
            MessageDb.conversation_id == conversation_id).order_by(MessageDb.created_at.asc())).all()
        chat_messages = [ChatMessageItem.model_validate(
            message.model_dump(mode="json")) for message in messages]
        data = {
            "total": len(chat_messages),
            "offset": 0,
            "limit": len(chat_messages),
            "messages": chat_messages
        }
        return ApiResponse.success(data=data, msg="获取消息列表成功")
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        return ApiResponse.error(code=1, msg=f"获取消息列表失败: {str(e)}")


@router.get("/detail/{conversation_id}")
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ApiResponse[ConversationInfo]:
    """Get a conversation by ID"""
    try:
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return ApiResponse.error(code=404, msg="对话不存在", data=None)
        logger.debug(f"Found conversation {conversation_id}")
        conversation_info = ConversationInfo.model_validate(
            conversation_to_dict(conversation))
        return ApiResponse.success(data=conversation_info, msg="获取对话详情成功")
    except Exception as e:
        logger.error(f"Failed to get conversation {conversation_id}: {e}")
        return ApiResponse.error(code=1, msg=f"获取对话详情失败: {str(e)}")


@router.put("/update/{conversation_id}")
async def update_conversation(conversation_id: str, request: UpdateConversationRequest, db: Session = Depends(get_db)) -> ApiResponse[ConversationInfo]:
    """Update a conversation by ID"""
    try:
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return ApiResponse.error(code=404, msg="对话不存在", data=None)
        conversation.title = request.title
        conversation.created_by = request.created_by
        conversation.updated_at = get_datetime_now()
        db.commit()
        db.refresh(conversation)
        return ApiResponse.success(data=conversation_to_dict(conversation), msg="更新对话成功")
    except Exception as e:
        logger.error(f"Failed to update conversation {conversation_id}: {e}")
        return ApiResponse.error(code=1, msg=f"更新对话失败: {str(e)}")


@router.delete("/delete/{conversation_id}")
async def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ApiResponse[str]:
    """Delete a conversation by ID"""
    try:
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            logger.error(f"Conversation {conversation_id} not found")
            return ApiResponse.error(code=404, msg="对话不存在", data=None)
        db.delete(conversation)
        db.commit()
        return ApiResponse.success(data=conversation_id, msg="删除对话成功")
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        return ApiResponse.error(code=1, msg=f"删除对话失败: {str(e)}")

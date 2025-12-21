"""对话服务"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import ConversationDb, MessageDb
from app.schemas.conversation import (
    ConversationInfo,
    CreatedBy,
    UpdateConversationRequest,
)
from app.schemas.chat import ChatMessageItem
from app.utils.date import get_datetime_now
from app.services.base_service import BaseService
from app.utils.logger import logger


class ConversationService(BaseService):
    """对话服务"""

    def __init__(self, db: Optional[Session] = None):
        """
        初始化对话服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        super().__init__(db)

    def conversation_to_dict(self, conversation: ConversationDb) -> dict:
        """Convert SQLModel Conversation instance to dict for ConversationInfo

        使用 mode="json" 自动将日期时间字段转换为 ISO 格式字符串
        """
        return conversation.model_dump(mode="json")

    def register_conversation(
        self, title: Optional[str], user_id: str
    ) -> ConversationInfo:
        """注册新对话"""
        db = self._ensure_db()
        conversation = ConversationDb(
            title=title or "新对话",
            created_by=CreatedBy.DEFAULT,
            user_id=user_id,
        )
        db.add(conversation)
        # 所有字段（id, created_at, updated_at 等）都通过 default_factory 在对象创建时生成
        # 不需要 refresh()，事务由 get_db() 自动提交
        logger.debug("Conversation registered",
                     conversation_id=conversation.id)
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def get_conversations(self, user_id: str) -> list[ConversationInfo]:
        """获取用户的所有对话"""
        db = self._ensure_db()
        conversations = db.exec(
            select(ConversationDb)
            .where(ConversationDb.user_id == user_id)
            .order_by(ConversationDb.last_message_created_at.desc())
        ).all()
        logger.debug("Found conversations", count=len(conversations))
        conversation_list = [
            ConversationInfo.model_validate(self.conversation_to_dict(conv))
            for conv in conversations
        ]
        return conversation_list

    def get_conversation(self, conversation_id: str) -> ConversationDb:
        """获取对话"""
        db = self._ensure_db()
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            logger.error("Conversation not found",
                         conversation_id=conversation_id)
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    def get_conversation_info(self, conversation_id: str) -> ConversationInfo:
        """获取对话信息"""
        conversation = self.get_conversation(conversation_id)
        logger.debug("Found conversation", conversation_id=conversation_id)
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def get_messages(self, conversation_id: str) -> list[ChatMessageItem]:
        """获取对话的消息列表"""
        db = self._ensure_db()
        # 先检查对话是否存在
        self.get_conversation(conversation_id)

        messages = db.exec(
            select(MessageDb)
            .where(MessageDb.conversation_id == conversation_id)
            .order_by(MessageDb.created_at.asc())
        ).all()
        chat_messages = [
            ChatMessageItem.model_validate(message.model_dump(mode="json"))
            for message in messages
        ]
        return chat_messages

    def update_conversation(
        self, conversation_id: str, request: UpdateConversationRequest
    ) -> ConversationInfo:
        """更新对话"""
        conversation = self.get_conversation(conversation_id)

        conversation.title = request.title
        conversation.created_by = request.created_by
        conversation.updated_at = get_datetime_now()
        # updated_at 已在代码中手动设置，不需要 refresh()
        # 事务由 get_db() 自动提交
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def delete_conversation(self, conversation_id: str) -> str:
        """删除对话"""
        db = self._ensure_db()
        conversation = self.get_conversation(conversation_id)
        db.delete(conversation)
        # 事务由 get_db() 自动提交
        return conversation_id

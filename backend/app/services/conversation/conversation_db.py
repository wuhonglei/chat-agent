"""对话 DB 服务"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import ConversationDb, MessageDb
from app.schemas.chat import ChatMessageItem
from app.schemas.conversation import (
    ConversationInfo,
    CreatedBy,
    UpdateConversationRequest,
)
from app.services.base_service.db_service import DbService
from app.utils.date import get_datetime_now
from app.utils.logger import logger


class ConversationDbService(DbService):
    """对话 DB 服务"""

    def __init__(self, db: Session | None = None):
        """
        初始化对话 DB 服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        super().__init__(db)

    def conversation_to_dict(self, conversation: ConversationDb) -> dict[str, Any]:
        """Convert SQLModel Conversation instance to dict for ConversationInfo

        使用 mode="json" 自动将日期时间字段转换为 ISO 格式字符串
        """
        return conversation.model_dump(mode="json")

    def register_conversation(
        self, title: str | None, user_id: str
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
        logger.debug("Conversation registered", conversation_id=conversation.id)
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
            .order_by(ConversationDb.last_message_created_at.desc())  # type: ignore[attr-defined]
        ).all()
        logger.debug("Found conversations", count=len(conversations))
        conversation_list = [
            ConversationInfo.model_validate(self.conversation_to_dict(conv))
            for conv in conversations
        ]
        return conversation_list

    def get_conversations_paginated(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[int, list[ConversationInfo]]:
        """分页获取用户的对话列表。

        Args:
            user_id: 用户 ID
            offset: 偏移量，默认 0
            limit: 每页数量，默认 20

        Returns:
            (总数, 当前页对话列表)
        """
        db = self._ensure_db()
        count_stmt = (
            select(func.count())
            .select_from(ConversationDb)
            .where(ConversationDb.user_id == user_id)
        )
        total = db.exec(count_stmt).one()
        data_stmt = (
            select(ConversationDb)
            .where(ConversationDb.user_id == user_id)
            .order_by(ConversationDb.last_message_created_at.desc())  # type: ignore[attr-defined]
            .offset(offset)
            .limit(limit)
        )
        conversations = db.exec(data_stmt).all()
        conversation_list = [
            ConversationInfo.model_validate(self.conversation_to_dict(conv))
            for conv in conversations
        ]
        logger.debug(
            "Found conversations (paginated)",
            total=total,
            offset=offset,
            limit=limit,
            returned=len(conversation_list),
        )
        return total, conversation_list

    def get_conversation(self, conversation_id: str) -> ConversationDb | None:
        """获取对话"""
        db = self._ensure_db()
        conversation = db.get(ConversationDb, conversation_id)
        return conversation

    def get_conversation_info(self, conversation_id: str) -> ConversationInfo | None:
        """获取对话信息"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def get_messages(self, conversation_id: str) -> list[ChatMessageItem]:
        """获取对话的消息列表"""
        db = self._ensure_db()
        messages = db.exec(
            select(MessageDb)
            .where(MessageDb.conversation_id == conversation_id)
            .order_by(MessageDb.created_at.asc())  # type: ignore[attr-defined]
        ).all()
        chat_messages = [
            ChatMessageItem.model_validate(message.model_dump(mode="json"))
            for message in messages
        ]
        return chat_messages

    def update_conversation(
        self, conversation: ConversationDb, request: UpdateConversationRequest
    ) -> ConversationInfo:
        """更新对话"""
        conversation.title = request.title
        conversation.created_by = request.created_by
        conversation.updated_at = get_datetime_now()
        # updated_at 已在代码中手动设置，不需要 refresh()
        # 事务由 get_db() 自动提交
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def delete_conversation(self, conversation: ConversationDb) -> str:
        """删除对话"""
        db = self._ensure_db()
        db.delete(conversation)
        # 事务由 get_db() 自动提交
        return conversation.id

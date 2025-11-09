from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.models.db import Conversation, Message, ToolCallMessage
from app.utils.common import get_datetime_now
from app.core.db import engine


class MessageService:
    """处理会话消息的入库与状态更新"""

    def __init__(self):
        pass

    def __enter__(self):
        self.db: Optional[Session] = Session(engine)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.db:
            self.db.close()
            self.db = None

    def _get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.db.get(Conversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    def _touch_conversation(
        self,
        conversation: Conversation,
        *,
        increment_count: bool = True,
    ) -> None:
        if increment_count:
            conversation.message_count = (conversation.message_count or 0) + 1
        conversation.updated_at = get_datetime_now()
        self.db.add(conversation)

    def _persist_message(
        self,
        message: Message,
        conversation: Conversation,
        *,
        increment_count: bool = True,
    ) -> Message:
        try:
            self._touch_conversation(
                conversation, increment_count=increment_count)
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            logger.info(f"message: {message}")
            return message
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "消息入库失败 conversation_id=%s role=%s error=%s",
                message.conversation_id,
                message.role,
                exc,
            )
            raise

    def create_user_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Message:
        conversation = self._get_conversation(conversation_id)
        message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            message_metadata=metadata or {},
            status="pending",
        )
        logger.info(f"user_message: {message}")
        return self._persist_message(message, conversation)

    def create_assistant_message(
        self,
        conversation_id: str,
        reply_to: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Message:
        conversation = self._get_conversation(conversation_id)
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            reasoning='',
            tool_calls=[],
            message_metadata=metadata or {},
            status="pending",
            reply_to=reply_to,
        )
        return self._persist_message(message, conversation)

    def update_assistant_message(
        self,
        message_id: str,
        *,
        content: Optional[str],
        reasoning: Optional[str],
        tool_calls: Optional[list[dict]],
        status: str,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> Message:
        persistent_message = self.db.get(Message, message_id)
        if not persistent_message:
            raise HTTPException(status_code=404, detail="助手消息不存在")

        persistent_message.status = status
        if content:
            persistent_message.content = content
        if reasoning:
            persistent_message.reasoning = reasoning
        if tool_calls:
            persistent_message.tool_calls = tool_calls
        if extra_metadata:
            merged_metadata = dict(persistent_message.message_metadata or {})
            merged_metadata.update(extra_metadata)
            persistent_message.message_metadata = merged_metadata
        self.db.add(persistent_message)
        self.db.commit()
        self.db.refresh(persistent_message)
        return persistent_message

    def mark_user_message_done(
        self,
        message_id: str,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Message]:
        return self._update_user_message_status(
            message_id,
            status="done",
            extra_metadata=extra_metadata,
        )

    def mark_user_message_failed(
        self,
        message_id: str,
        error_message: str,
    ) -> Optional[Message]:
        return self._update_user_message_status(
            message_id,
            status="failed",
            extra_metadata={"error": error_message},
        )

    def _update_user_message_status(
        self,
        message_id: str,
        *,
        status: str,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Message]:
        message = self.db.get(Message, message_id)
        if not message:
            logger.warning("未找到待更新的用户消息 message_id=%s", message_id)
            return None

        try:
            message.status = status
            if extra_metadata:
                merged_metadata = dict(message.message_metadata or {})
                merged_metadata.update(extra_metadata)
                message.message_metadata = merged_metadata

            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "更新消息状态失败 message_id=%s status=%s error=%s",
                message_id,
                status,
                exc,
            )
            raise

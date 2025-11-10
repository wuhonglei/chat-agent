from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select, delete

from app.models.chat import ChatMessageItemReq, MessageStatus
from app.models.db import Conversation, Message
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

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.db.get(Conversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    def remove_messages(self, message_ids: list[str]) -> None:
        if not message_ids:
            return True
        self.db.exec(delete(Message).where(Message.id.in_(message_ids)))
        self.db.commit()
        return True

    def get_messages_by_ids(self, message_ids: list[str]) -> list[ChatMessageItemReq]:
        if not message_ids:
            return []

        messages = self.db.exec(select(Message.role, Message.content).where(
            Message.id.in_(message_ids))).all()
        if not messages:
            logger.error(f"消息不存在: {message_ids}")
            return []

        return [ChatMessageItemReq(role=message[0], content=message[1]) for message in messages]

    def _touch_conversation(
        self,
        conversation: Conversation,
    ) -> None:
        conversation.last_message_created_at = get_datetime_now()
        self.db.add(conversation)

    def _persist_message(
        self,
        message: Message,
        conversation: Conversation,
    ) -> Message:
        try:
            self._touch_conversation(conversation)
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
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
        conversation: Conversation,
        message_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Message:
        message = Message(
            id=message_id,
            conversation_id=conversation.id,
            role="user",
            content=content,
            message_metadata=metadata or {},
            status=MessageStatus.DONE,
        )
        return self._persist_message(message, conversation)

    def create_assistant_message(
        self,
        conversation: Conversation,
        message_id: str,
        reply_to: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Message:
        message = Message(
            id=message_id,
            conversation_id=conversation.id,
            role="assistant",
            content="",
            reasoning='',
            tool_calls=[],
            message_metadata=metadata or {},
            status=MessageStatus.PENDING,
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
        status: MessageStatus,
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

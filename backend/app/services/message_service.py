from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select, delete

from app.models.chat import ChatMessageItem, ChatMessageItemReq, CollectedResponse, MessageStatus
from app.models.db import ConversationDb, MessageDb
from app.utils.date import get_datetime_now
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

    def get_conversation(self, conversation_id: str) -> ConversationDb:
        conversation = self.db.get(ConversationDb, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    def remove_messages(self, message_ids: list[str]) -> None:
        if not message_ids:
            return True
        self.db.exec(delete(MessageDb).where(MessageDb.id.in_(message_ids)))
        self.db.commit()
        return True

    def get_flatten_messages_by_ids(self, message_ids: list[str]) -> list[ChatMessageItemReq]:
        """获取消息的扁平化列表
        组装顺序参考: https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
        """
        if not message_ids:
            return []

        messages = self.db.exec(select(MessageDb.id, MessageDb.role, MessageDb.content, MessageDb.tool_calls).where(
            MessageDb.id.in_(message_ids))).all()
        if not messages:
            from app.utils.logger import logger
            logger.error("Messages not found", message_ids=message_ids)
            return []

        # 创建字典映射，key 为 message_id，value 为消息元组
        messages_dict = {msg[0]: msg for msg in messages}

        flattened_messages: list[ChatMessageItemReq] = []
        # 按照 message_ids 的顺序遍历，保证返回顺序一致
        for message_id in message_ids:
            if message_id not in messages_dict:
                from app.utils.logger import logger
                logger.warning("Message ID not found, skipping",
                               message_id=message_id)
                continue

            id, role, content, tool_call_messages = messages_dict[message_id]
            # 将工具调用消息拼接到消息中
            for tool_call_message in tool_call_messages or []:
                tool_role = tool_call_message.get('role')
                if tool_role == 'assistant':
                    flattened_messages.append(ChatMessageItemReq(
                        role='assistant', tool_calls=tool_call_message['tool_calls']))
                elif tool_role == 'tool':
                    flattened_messages.append(ChatMessageItemReq(
                        role='tool', tool_call_id=tool_call_message['tool_call_id'], content=tool_call_message['content']))

            # 将用户问题或模型最终回答拼接到消息中
            flattened_messages.append(
                ChatMessageItemReq(role=role, content=content))

        return flattened_messages

    def _touch_conversation(
        self,
        conversation: ConversationDb,
        last_message_created_at: datetime,
        last_message_updated_at: datetime,
    ) -> None:
        conversation.last_message_created_at = last_message_created_at
        conversation.last_message_updated_at = last_message_updated_at
        self.db.add(conversation)

    def _persist_message(
        self,
        message: MessageDb,
        conversation: ConversationDb,
    ) -> MessageDb:
        try:
            self._touch_conversation(
                conversation, message.created_at, message.updated_at)
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except SQLAlchemyError as exc:
            self.db.rollback()
            from app.utils.logger import logger
            logger.error(
                "Failed to persist message",
                error=exc,
                conversation_id=message.conversation_id,
                role=message.role,
            )
            raise

    def create_user_message(
        self,
        conversation: ConversationDb,
        message_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MessageDb:
        message = MessageDb(
            id=message_id,
            role="user",
            content=content,
            conversation_id=conversation.id,
            message_metadata=metadata or {},
            status=MessageStatus.DONE,
        )
        return self._persist_message(message, conversation)

    def create_assistant_message(
        self,
        conversation: ConversationDb,
        message_id: str,
        reply_to: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MessageDb:
        message = MessageDb(
            id=message_id,
            role="assistant",
            content="",
            reasoning='',
            tool_calls=[],
            conversation_id=conversation.id,
            message_metadata=metadata or {},
            status=MessageStatus.PENDING,
            reply_to=reply_to,
        )
        return self._persist_message(message, conversation)

    def update_assistant_message(
        self,
        conversation: ConversationDb,
        assistant_message: MessageDb,
        *,
        assistant_payload: CollectedResponse,
        status: MessageStatus,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> MessageDb:
        assistant_message.status = status
        assistant_message.updated_at = get_datetime_now()
        if assistant_payload.content:
            assistant_message.content = assistant_payload.content
        if assistant_payload.reasoning:
            assistant_message.reasoning = assistant_payload.reasoning
        if assistant_payload.tool_calls:
            assistant_message.tool_calls = assistant_payload.tool_calls
        if assistant_payload.tool_calls_duration:
            assistant_message.tool_calls_duration = assistant_payload.tool_calls_duration
        if assistant_payload.reasoning_duration:
            assistant_message.reasoning_duration = assistant_payload.reasoning_duration
        if assistant_payload.content_duration:
            assistant_message.content_duration = assistant_payload.content_duration
        if assistant_payload.total_duration:
            assistant_message.total_duration = assistant_payload.total_duration
        if extra_metadata:
            merged_metadata = dict(assistant_message.message_metadata or {})
            merged_metadata.update(extra_metadata)
            assistant_message.message_metadata = merged_metadata
        return self._persist_message(assistant_message, conversation)

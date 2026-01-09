from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select, delete

from app.schemas.chat import ChatMessageItemReq, CollectedResponse, MessageStatus
from app.models import ConversationDb, MessageDb
from app.utils.date import get_datetime_now
from app.services.base_service import BaseService


class MessageService(BaseService):
    """处理会话消息的入库与状态更新"""

    def __init__(self, db: Optional[Session] = None):
        """
        初始化消息服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        super().__init__(db)

    def get_conversation(self, conversation_id: str) -> ConversationDb:
        """获取对话"""
        db = self._ensure_db()
        conversation = db.get(ConversationDb, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    def remove_messages(self, message_ids: list[str]) -> None:
        """删除消息"""
        if not message_ids:
            return
        db = self._ensure_db()
        db.exec(delete(MessageDb).where(MessageDb.id.in_(message_ids)))
        # 事务由 get_db() 或 BaseService.__exit__ 自动提交

    def get_flatten_messages_by_ids(self, message_ids: list[str]) -> list[ChatMessageItemReq]:
        """获取消息的扁平化列表
        组装顺序参考: https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
        """
        if not message_ids:
            return []

        db = self._ensure_db()
        messages = db.exec(select(MessageDb.id, MessageDb.role, MessageDb.content, MessageDb.tool_calls).where(
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
        """更新对话的最后消息时间"""
        conversation.last_message_created_at = last_message_created_at
        conversation.last_message_updated_at = last_message_updated_at
        db = self._ensure_db()
        db.add(conversation)

    def _persist_message(
        self,
        message: MessageDb,
        conversation: ConversationDb,
    ) -> MessageDb:
        """持久化消息到数据库

        注意：此方法需要立即提交事务（用于流式响应场景），
        因此手动调用 commit()，而不是依赖自动提交。
        """
        db = self._ensure_db()
        try:
            self._touch_conversation(
                conversation, message.created_at, message.updated_at)
            db.add(message)
            # 流式响应需要立即看到数据，所以手动提交
            # 如果使用依赖注入的 db，这里提交后 get_db() 不会再提交（已提交的事务不会重复提交）
            db.commit()
            # 所有字段都有 default_factory 或手动设置，不需要 refresh()
            # 注意：commit() 后对象变为 Detached 状态，refresh() 会报错
            return message
        except SQLAlchemyError as exc:
            db.rollback()
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
            component_tool_calls=[],
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
        if assistant_payload.component_tool_calls:
            assistant_message.component_tool_calls = assistant_payload.component_tool_calls
        if assistant_payload.component_tool_calls_duration:
            assistant_message.component_tool_calls_duration = assistant_payload.component_tool_calls_duration
        if assistant_payload.reasoning_duration:
            assistant_message.reasoning_duration = assistant_payload.reasoning_duration
        if assistant_payload.content_duration:
            assistant_message.content_duration = assistant_payload.content_duration
        if assistant_payload.total_duration:
            assistant_message.total_duration = assistant_payload.total_duration
        if assistant_payload.token_stats:
            assistant_message.token_stats = assistant_payload.token_stats
        if extra_metadata:
            merged_metadata = dict(assistant_message.message_metadata or {})
            merged_metadata.update(extra_metadata)
            assistant_message.message_metadata = merged_metadata
        return self._persist_message(assistant_message, conversation)

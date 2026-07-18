"""对话 DB 服务"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models import ConversationDb, MessageDb
from app.schemas.chat import ChatMessage, dump_content_block_payloads
from app.schemas.conversation import (
    ConversationInfo,
    ConversationListResponse,
    CreatedBy,
    UpdateConversationRequest,
)
from app.services.base_service.db_service import DbService
from app.utils.cursor import (
    decode_conversation_cursor,
    encode_conversation_cursor,
)
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
        self, title: str | None, user_id: str, is_active: bool = True
    ) -> ConversationInfo:
        """注册新对话"""
        db = self._ensure_db()
        conversation = ConversationDb(
            title=title or "新对话",
            created_by=CreatedBy.DEFAULT,
            user_id=user_id,
            is_active=is_active,
        )
        db.add(conversation)
        # 先构建返回数据，再提交事务。
        # SQLAlchemy 在 commit 后会过期对象状态，直接 model_dump 可能拿到空对象。
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        # 显式提交，避免“注册成功后紧接着发首条消息”时被下一请求读不到会话的竞态。
        # 对依赖注入场景而言，即便 get_db() 在请求收尾再次 commit，也不会产生副作用。
        db.commit()
        return conversation_info

    def get_conversations(self, user_id: str) -> list[ConversationInfo]:
        """获取用户的所有对话"""
        db = self._ensure_db()
        last_message_created_at_column = cast(
            Any, ConversationDb.last_message_created_at
        )
        conversations = db.exec(
            select(ConversationDb)
            .where(ConversationDb.user_id == user_id)
            .where(ConversationDb.is_active)
            .order_by(last_message_created_at_column.desc())
        ).all()
        logger.debug("Found conversations", count=len(conversations))
        conversation_list = [
            ConversationInfo.model_validate(self.conversation_to_dict(conv))
            for conv in conversations
        ]
        return conversation_list

    def get_conversations_paginated(
        self,
        user_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ConversationListResponse:
        """游标分页获取用户的对话列表。

        按 (last_message_created_at DESC, id DESC) keyset 分页。
        非法 cursor 会抛出 InvalidCursorError。
        """
        db = self._ensure_db()
        last_message_created_at_column = cast(
            Any, ConversationDb.last_message_created_at
        )
        id_column = cast(Any, ConversationDb.id)

        data_stmt = (
            select(ConversationDb)
            .where(ConversationDb.user_id == user_id)
            .where(ConversationDb.is_active)
        )
        if cursor:
            cursor_values = decode_conversation_cursor(cursor)
            data_stmt = data_stmt.where(
                or_(
                    last_message_created_at_column
                    < cursor_values.last_message_created_at,
                    and_(
                        last_message_created_at_column
                        == cursor_values.last_message_created_at,
                        id_column < cursor_values.id,
                    ),
                )
            )

        data_stmt = data_stmt.order_by(
            last_message_created_at_column.desc(),
            id_column.desc(),
        ).limit(limit + 1)

        conversations = list(db.exec(data_stmt).all())
        has_more = len(conversations) > limit
        page_rows = conversations[:limit]
        conversation_list = [
            ConversationInfo.model_validate(self.conversation_to_dict(conv))
            for conv in page_rows
        ]

        next_cursor: str | None = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_conversation_cursor(
                last.last_message_created_at, last.id
            )

        logger.debug(
            "Found conversations (cursor paginated)",
            limit=limit,
            returned=len(conversation_list),
            has_more=has_more,
        )
        return ConversationListResponse(
            conversations=conversation_list,
            next_cursor=next_cursor,
            has_more=has_more,
            limit=limit,
        )


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


    def activate_conversation(self, conversation: ConversationDb) -> ConversationInfo:
        """激活草稿会话，使其出现在会话列表中。"""
        conversation.is_active = True
        conversation.updated_at = get_datetime_now()
        conversation_info = ConversationInfo.model_validate(
            self.conversation_to_dict(conversation)
        )
        return conversation_info

    def get_messages(
        self,
        conversation_id: str,
        omit_tool_result_content_and_summary_when_structured: bool = False,
    ) -> list[dict[str, Any]]:
        """获取对话的消息列表"""
        db = self._ensure_db()
        created_at_column = cast(Any, MessageDb.created_at)
        messages = db.exec(
            select(MessageDb)
            .where(MessageDb.conversation_id == conversation_id)
            .order_by(created_at_column.asc())
        ).all()
        chat_messages: list[dict[str, Any]] = []
        for message in messages:
            payload = message.model_dump(mode="json")
            chat_message = ChatMessage.model_validate(payload)
            chat_message_payload = chat_message.model_dump(mode="json")
            chat_message_payload["content_blocks"] = dump_content_block_payloads(
                chat_message.content_blocks,
                omit_tool_result_content_and_summary_when_structured=omit_tool_result_content_and_summary_when_structured,
            )
            chat_messages.append(chat_message_payload)
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

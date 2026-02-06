"""会话级上下文 DB 服务（conversation_contexts 表：窗口外摘要）"""

from __future__ import annotations

from sqlmodel import select

from app.models import ConversationContextDb
from app.services.base_service import BaseService
from app.utils.logger import logger


class ConversationContextDbService(BaseService):
    """会话级上下文（conversation_contexts）DB 读写"""

    def get_conversation_context(
        self, user_id: str, conversation_id: str
    ) -> ConversationContextDb | None:
        """按 user_id + conversation_id 查询会话级上下文（窗口外摘要）"""
        db = self._ensure_db()
        return db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.user_id == user_id,
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()

    def upsert_conversation_context(
        self,
        user_id: str,
        conversation_id: str,
        *,
        summary_before_window: str | None = None,
        recent_summary: str | None = None,
    ) -> ConversationContextDb:
        """插入或更新会话级上下文；仅更新传入的非 None 字段"""
        db = self._ensure_db()
        row = db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.user_id == user_id,
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()
        if row:
            if summary_before_window is not None:
                row.summary_before_window = summary_before_window
            if recent_summary is not None:
                row.recent_summary = recent_summary
            db.add(row)
        else:
            row = ConversationContextDb(
                user_id=user_id,
                conversation_id=conversation_id,
                summary_before_window=summary_before_window,
                recent_summary=recent_summary,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        logger.debug(
            "Upserted conversation_context",
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return row

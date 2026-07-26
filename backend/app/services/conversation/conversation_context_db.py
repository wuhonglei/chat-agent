"""会话级上下文 DB 服务（conversation_contexts 表：窗口外摘要）"""

from __future__ import annotations

from sqlmodel import select

from app.models import ConversationContextDb
from app.services.base_service.db_service import DbService
from app.utils.date import get_datetime_now
from app.utils.logger import logger


class ConversationContextDbService(DbService):
    """会话级上下文（conversation_contexts）DB 读写"""

    def get_conversation_context(
        self, conversation_id: str
    ) -> ConversationContextDb | None:
        """按 conversation_id 查询会话级上下文（窗口外摘要）"""
        db = self._ensure_db()
        return db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()

    def upsert_conversation_context(
        self,
        conversation_id: str,
        *,
        summary_before_window: str | None = None,
        last_summarized_message_ids: list[str] | None = None,
    ) -> ConversationContextDb:
        """插入或更新会话级上下文；仅更新传入的非 None 字段"""
        db = self._ensure_db()
        row = db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()
        if row:
            if summary_before_window is not None:
                row.summary_before_window = summary_before_window
            if last_summarized_message_ids is not None:
                row.last_summarized_message_ids = last_summarized_message_ids
            db.add(row)
        else:
            row = ConversationContextDb(
                conversation_id=conversation_id,
                summary_before_window=summary_before_window,
                last_summarized_message_ids=last_summarized_message_ids,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        logger.debug(
            "Upserted conversation_context",
            conversation_id=conversation_id,
        )
        return row

    def get_conversation_context_summary(
        self,
        conversation_id: str,
    ) -> str | None:
        """获取会话级上下文摘要"""
        context = self.get_conversation_context(conversation_id)
        if context and context.summary_before_window:
            raw = context.summary_before_window.strip()
            if raw:
                return raw

        return None

    def increment_summary_failure_count(self, conversation_id: str) -> None:
        db = self._ensure_db()
        row = db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()
        if row is None:
            row = ConversationContextDb(
                conversation_id=conversation_id,
                summary_failure_count=1,
                last_summary_failure_at=get_datetime_now(),
            )
        else:
            row.summary_failure_count = int(row.summary_failure_count or 0) + 1
            row.last_summary_failure_at = get_datetime_now()
        db.add(row)
        db.commit()

    def reset_summary_failure_count(self, conversation_id: str) -> None:
        db = self._ensure_db()
        row = db.exec(
            select(ConversationContextDb).where(
                ConversationContextDb.conversation_id == conversation_id,
            )
        ).first()
        if row is None:
            return
        row.summary_failure_count = 0
        row.last_summary_failure_at = None
        db.add(row)
        db.commit()

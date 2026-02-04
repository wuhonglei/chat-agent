"""用户画像与会话上下文服务（user_profile 跨会话 + user_context 会话级）"""

from __future__ import annotations

from sqlmodel import select

from app.models import UserContextDb, UserProfileDb
from app.services.base_service import BaseService
from app.utils.logger import logger


class UserProfileService(BaseService):
    """用户画像与会话上下文的读写"""

    def get_user_profile(self, user_id: str) -> UserProfileDb | None:
        """按 user_id 查询用户画像（事实与偏好）"""
        db = self._ensure_db()
        return db.exec(
            select(UserProfileDb).where(UserProfileDb.user_id == user_id)
        ).first()

    def upsert_user_profile(
        self,
        user_id: str,
        *,
        facts: list[str] | None = None,
        preferences: list[str] | None = None,
    ) -> UserProfileDb:
        """插入或更新用户画像；仅更新传入的非 None 字段"""
        db = self._ensure_db()
        row = db.exec(
            select(UserProfileDb).where(UserProfileDb.user_id == user_id)
        ).first()
        if row:
            if facts is not None:
                row.facts = facts
            if preferences is not None:
                row.preferences = preferences
            db.add(row)
        else:
            row = UserProfileDb(
                user_id=user_id,
                facts=facts or [],
                preferences=preferences or [],
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def get_user_context(
        self, user_id: str, conversation_id: str
    ) -> UserContextDb | None:
        """按 user_id + conversation_id 查询会话级上下文（窗口外摘要）"""
        db = self._ensure_db()
        return db.exec(
            select(UserContextDb).where(
                UserContextDb.user_id == user_id,
                UserContextDb.conversation_id == conversation_id,
            )
        ).first()

    def upsert_user_context(
        self,
        user_id: str,
        conversation_id: str,
        *,
        summary_before_window: str | None = None,
        recent_summary: str | None = None,
    ) -> UserContextDb:
        """插入或更新会话级上下文；仅更新传入的非 None 字段"""
        db = self._ensure_db()
        row = db.exec(
            select(UserContextDb).where(
                UserContextDb.user_id == user_id,
                UserContextDb.conversation_id == conversation_id,
            )
        ).first()
        if row:
            if summary_before_window is not None:
                row.summary_before_window = summary_before_window
            if recent_summary is not None:
                row.recent_summary = recent_summary
            db.add(row)
        else:
            row = UserContextDb(
                user_id=user_id,
                conversation_id=conversation_id,
                summary_before_window=summary_before_window,
                recent_summary=recent_summary,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        logger.debug(
            "Upserted user_context",
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return row

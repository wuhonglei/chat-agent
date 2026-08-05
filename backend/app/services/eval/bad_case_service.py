"""低分复核队列服务"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.models.bad_case_item_db import BadCaseItemDb
from app.schemas.eval import (
    BadCaseAttribution,
    BadCaseItemResponse,
    BadCaseListResponse,
    BadCaseSource,
    BadCaseStatsResponse,
    BadCaseStatus,
    BadCaseUpdateRequest,
)
from app.services.base_service.db_service import DbService
from app.utils.date import get_datetime_now
from app.utils.logger import logger


class BadCaseService(DbService):
    """低分复核队列 CRUD + 自动入队"""

    def __init__(self, db: Session | None = None):
        super().__init__(db)

    # ── 创建 ──

    def enqueue(
        self,
        *,
        source: BadCaseSource,
        message_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        query: str = "",
        answer: str = "",
        rule_scores: dict[str, Any] | None = None,
        judge_scores: dict[str, Any] | None = None,
        trace_id: str | None = None,
        feedback_reasons: list[str] | None = None,
        feedback_comment: str | None = None,
    ) -> BadCaseItemDb:
        """将一条 bad case 加入复核队列。去重：同一 message_id + source 不重复入队。"""
        db = self._ensure_db()

        # 去重
        if message_id:
            existing = db.exec(
                select(BadCaseItemDb).where(
                    BadCaseItemDb.message_id == message_id,
                    BadCaseItemDb.source == source.value,
                )
            ).first()
            if existing:
                logger.debug(
                    "Bad case already queued",
                    message_id=message_id,
                    source=source.value,
                )
                return existing

        item = BadCaseItemDb(
            source=source.value,
            message_id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
            query=query[:500],
            answer=answer[:1000],
            rule_scores=rule_scores or {},
            judge_scores=judge_scores,
            trace_id=trace_id,
            feedback_reasons=feedback_reasons or [],
            feedback_comment=feedback_comment,
            status=BadCaseStatus.PENDING.value,
        )
        db.add(item)
        db.flush()
        logger.info(
            "Bad case enqueued",
            item_id=item.id,
            source=source.value,
            query=query[:80],
        )
        return item

    # ── 查询 ──

    def list_items(
        self,
        *,
        status: BadCaseStatus | None = None,
        source: BadCaseSource | None = None,
        attribution: BadCaseAttribution | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BadCaseListResponse:
        """分页查询 bad case 列表。"""
        db = self._ensure_db()
        stmt = select(BadCaseItemDb)

        if status:
            stmt = stmt.where(BadCaseItemDb.status == status.value)
        if source:
            stmt = stmt.where(BadCaseItemDb.source == source.value)
        if attribution:
            stmt = stmt.where(BadCaseItemDb.attribution == attribution.value)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.exec(count_stmt).one()

        # 分页
        stmt = stmt.order_by(desc(BadCaseItemDb.created_at))  # type: ignore[arg-type]
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(db.exec(stmt).all())

        return BadCaseListResponse(
            items=[self._to_response(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_item(self, item_id: str) -> BadCaseItemDb | None:
        """获取单条 bad case。"""
        return self._ensure_db().get(BadCaseItemDb, item_id)

    # ── 更新 ──

    def update_item(
        self, item_id: str, request: BadCaseUpdateRequest
    ) -> BadCaseItemDb | None:
        """更新 bad case（人工归因/处理）。"""
        db = self._ensure_db()
        item = db.get(BadCaseItemDb, item_id)
        if not item:
            return None

        now = get_datetime_now()

        if request.status is not None:
            item.status = request.status.value
            if request.status == BadCaseStatus.REVIEWING and item.reviewed_at is None:
                item.reviewed_at = now
            if request.status in (
                BadCaseStatus.RESOLVED,
                BadCaseStatus.DISMISSED,
            ):
                item.resolved_at = now

        if request.attribution is not None:
            item.attribution = request.attribution.value
        if request.reviewer_notes is not None:
            item.reviewer_notes = request.reviewer_notes
        if request.resolution is not None:
            item.resolution = request.resolution.value

        db.add(item)
        db.flush()
        return item

    # ── 统计 ──

    def get_stats(self) -> BadCaseStatsResponse:
        """获取 bad case 队列统计。"""
        db = self._ensure_db()

        total = db.exec(select(func.count()).select_from(BadCaseItemDb)).one()

        # 按 status 分组
        by_status: dict[str, int] = {}
        rows = db.exec(
            select(BadCaseItemDb.status, func.count()).group_by(BadCaseItemDb.status)
        ).all()
        by_status = {r[0]: r[1] for r in rows}

        # 按 source 分组
        rows = db.exec(
            select(BadCaseItemDb.source, func.count()).group_by(BadCaseItemDb.source)
        ).all()
        by_source = {r[0]: r[1] for r in rows}

        # 按 attribution 分组（排除 NULL）
        attribution_rows = db.exec(
            select(BadCaseItemDb.attribution, func.count())
            .where(BadCaseItemDb.attribution.isnot(None))  # type: ignore[union-attr]
            .group_by(BadCaseItemDb.attribution)
        ).all()
        by_attribution: dict[str, int] = {
            attr: count for attr, count in attribution_rows if attr is not None
        }

        return BadCaseStatsResponse(
            total=total,
            by_status=by_status,
            by_source=by_source,
            by_attribution=by_attribution,
        )

    def dismiss_by_message(self, message_id: str) -> int:
        """取消点踩时，将该 message 的 pending 状态的 thumb_down case 标记为 dismissed。返回处理条数。"""
        db = self._ensure_db()
        now = get_datetime_now()
        items = db.exec(
            select(BadCaseItemDb).where(
                BadCaseItemDb.message_id == message_id,
                BadCaseItemDb.source == BadCaseSource.THUMB_DOWN.value,
                BadCaseItemDb.status == BadCaseStatus.PENDING.value,
            )
        ).all()
        count = 0
        for item in items:
            item.status = BadCaseStatus.DISMISSED.value
            item.resolved_at = now
            item.reviewer_notes = "用户取消点踩，自动 dismiss"
            db.add(item)
            count += 1
        if count:
            db.flush()
            logger.info(
                "Bad cases dismissed by thumb-down cancel",
                message_id=message_id,
                count=count,
            )
        return count

    # ── 内部 ──

    @staticmethod
    def _to_response(item: BadCaseItemDb) -> BadCaseItemResponse:
        return BadCaseItemResponse.model_validate(item.model_dump(mode="json"))

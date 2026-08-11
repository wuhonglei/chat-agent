"""低分复核队列服务"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.observability import (
    build_trace_url,
    ensure_dataset,
    get_langfuse,
    new_trace_id,
)
from app.models.bad_case_item_db import BadCaseItemDb
from app.schemas.eval import (
    BadCaseAttribution,
    BadCaseItemResponse,
    BadCaseListResponse,
    BadCaseResolution,
    BadCaseSource,
    BadCaseStatsResponse,
    BadCaseStatus,
    BadCaseUpdateRequest,
)
from app.services.base_service.db_service import DbService
from app.services.eval.judge_input_builder import (
    extract_generation_answer,
    fetch_last_generation,
    normalize_generation_input,
)
from app.utils.date import get_datetime_now
from app.utils.logger import logger

DATASET_ITEM_VERSION = "v1.0"


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
            items=[self.to_response(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_item(self, item_id: str) -> BadCaseItemDb | None:
        """获取单条 bad case。"""
        return self._ensure_db().get(BadCaseItemDb, item_id)

    def delete_item(self, item_id: str) -> bool:
        """删除单条 bad case。不存在返回 False。"""
        db = self._ensure_db()
        item = db.get(BadCaseItemDb, item_id)
        if not item:
            return False
        db.delete(item)
        db.flush()
        logger.info("Bad case deleted", item_id=item_id)
        return True

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

    def add_to_dataset(self, item_id: str) -> BadCaseItemDb:
        """将 bad case 推送到固定 Langfuse dataset，并标记为已解决。

        Dataset item 结构对齐离线评估集（prod_trace）：
        - input / expected_output：取自 trace 下最后一条 GENERATION observation
        - metadata：source / user_id / version / trace_id / agent_mode / session_id
        """
        db = self._ensure_db()
        item = db.get(BadCaseItemDb, item_id)
        if item is None:
            raise LookupError("bad case 不存在")

        langfuse = get_langfuse()
        if langfuse is None:
            raise RuntimeError("Langfuse 客户端不可用")

        dataset_name = settings.langfuse.bad_case_dataset_name
        ensure_dataset(
            dataset_name,
            description="Bad cases from chat-agent review queue",
        )

        payload = self._build_dataset_item_payload(item, langfuse)
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            id=item.id,
            **payload,
        )

        now = get_datetime_now()
        item.resolution = BadCaseResolution.ADDED_TO_DATASET.value
        item.status = BadCaseStatus.RESOLVED.value
        if item.resolved_at is None:
            item.resolved_at = now
        if item.reviewed_at is None:
            item.reviewed_at = now
        db.add(item)
        db.flush()
        logger.info(
            "Bad case added to Langfuse dataset",
            item_id=item.id,
            dataset_name=dataset_name,
            from_generation=bool(payload.get("source_observation_id")),
        )
        return item

    @staticmethod
    def _build_dataset_item_payload(
        item: BadCaseItemDb,
        langfuse: Any,
    ) -> dict[str, Any]:
        """组装 create_dataset_item 参数，优先 last GENERATION IO。"""
        trace_id = item.trace_id or (
            new_trace_id(item.message_id) if item.message_id else None
        )
        generation = fetch_last_generation(langfuse, trace_id or "")
        source_observation_id: str | None = None
        agent_mode = 0
        dataset_input: dict[str, Any]
        expected_output: str | None

        if generation is not None:
            source_observation_id = str(generation.get("id") or "").strip() or None
            gen_meta = generation.get("metadata") or {}
            if isinstance(gen_meta, dict):
                raw_mode = gen_meta.get("agent_mode")
                if isinstance(raw_mode, int):
                    agent_mode = raw_mode
                elif isinstance(raw_mode, str) and raw_mode.isdigit():
                    agent_mode = int(raw_mode)

            dataset_input = normalize_generation_input(generation.get("input"))
            messages = dataset_input.get("messages")
            if not isinstance(messages, list) or not messages:
                query = (item.query or "").strip()
                dataset_input = {
                    "messages": ([{"role": "user", "content": query}] if query else [])
                }

            expected_output = (
                extract_generation_answer(generation.get("output"))
                or (item.answer or "").strip()
                or None
            )
        else:
            query = (item.query or "").strip()
            dataset_input = {
                "messages": ([{"role": "user", "content": query}] if query else [])
            }
            expected_output = (item.answer or "").strip() or None

        judge_scores = item.judge_scores if isinstance(item.judge_scores, dict) else {}
        metadata: dict[str, Any] = {
            "source": "prod_trace",
            "user_id": item.user_id,
            "version": DATASET_ITEM_VERSION,
            "trace_id": trace_id,
            "agent_mode": agent_mode,
            "session_id": item.conversation_id,
            # 复核队列溯源字段
            "bad_case_id": item.id,
            "bad_case_source": item.source,
            "message_id": item.message_id,
            "attribution": item.attribution,
            "rule_scores": item.rule_scores or {},
            "judge_scores": judge_scores or None,
        }

        return {
            "input": dataset_input,
            "expected_output": expected_output,
            "metadata": metadata,
            "source_trace_id": trace_id,
            "source_observation_id": source_observation_id,
        }

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

    def update_judge_scores(
        self,
        *,
        message_id: str,
        source: BadCaseSource,
        judge_scores: dict[str, Any],
    ) -> BadCaseItemDb | None:
        """回写裁判分数到已有 bad case（如 thumb_down 补评）。"""
        if not message_id:
            return None
        db = self._ensure_db()
        item = db.exec(
            select(BadCaseItemDb).where(
                BadCaseItemDb.message_id == message_id,
                BadCaseItemDb.source == source.value,
            )
        ).first()
        if not item:
            return None
        item.judge_scores = judge_scores
        db.add(item)
        db.flush()
        return item

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
    def to_response(item: BadCaseItemDb) -> BadCaseItemResponse:
        data = item.model_dump(mode="json")
        # 历史点踩入队可能未落库 trace_id；有 message_id 时用与 chat-turn 相同规则回推
        trace_id = item.trace_id or (
            new_trace_id(item.message_id) if item.message_id else None
        )
        data["trace_id"] = trace_id
        data["langfuse_trace_url"] = build_trace_url(trace_id)
        return BadCaseItemResponse.model_validate(data)

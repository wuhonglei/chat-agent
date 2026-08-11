"""批量评估编排：拉取 Trace → 分层采样 → 裁判打分 → 入 bad case 队列。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.observability import get_langfuse
from app.evaluators.judge_evaluator import JudgeResult, LLMCaller, call_judge_model
from app.evaluators.sampler import sample_rates_from_config, stratified_sample
from app.models.bad_case_item_db import BadCaseItemDb
from app.models.eval_run_log_db import EvalRunLog
from app.schemas.eval import BadCaseSource
from app.services.eval.bad_case_service import BadCaseService
from app.services.eval.judge_input_builder import JudgeInputBuilder
from app.services.eval.score_summary import build_score_summary
from app.utils.date import get_datetime_now
from app.utils.logger import logger

JUDGE_SCORE_PREFIX = "judge_"
TRACE_PAGE_SIZE = 50
TERMINAL_EXCLUDE_STATUSES = frozenset[str]({"stopped", "failed"})
CHAT_TURN_OBSERVATION_NAME = "chat-turn"


def _trace_to_dict(trace: Any) -> dict[str, Any]:
    if isinstance(trace, dict):
        return cast(dict[str, Any], trace)
    if hasattr(trace, "model_dump"):
        return cast(dict[str, Any], trace.model_dump())
    if hasattr(trace, "dict"):
        return cast(dict[str, Any], trace.dict())
    return dict(trace)


def _metadata(trace: dict[str, Any]) -> dict[str, Any]:
    meta = trace.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _message_id(trace: dict[str, Any]) -> str:
    meta = _metadata(trace)
    return str(meta.get("assistant_message_id") or meta.get("message_id") or "")


def _score_names(trace: dict[str, Any]) -> set[str]:
    scores = trace.get("scores") or []
    if not isinstance(scores, list):
        return set()
    names: set[str] = set()
    for s in scores:
        if isinstance(s, dict) and s.get("name"):
            names.add(str(s["name"]))
    return names


def _score_map(trace: dict[str, Any]) -> dict[str, Any]:
    scores = trace.get("scores") or []
    if not isinstance(scores, list):
        return {}
    result: dict[str, Any] = {}
    for s in scores:
        if isinstance(s, dict) and s.get("name"):
            result[str(s["name"])] = s.get("value")
    return result


def _has_valid_answer_score(trace: dict[str, Any]) -> bool:
    return "valid_answer" in _score_names(trace)


def _has_judge_scores(trace: dict[str, Any]) -> bool:
    return any(name.startswith(JUDGE_SCORE_PREFIX) for name in _score_names(trace))


def _trace_status(trace: dict[str, Any]) -> str:
    meta = _metadata(trace)
    return str(meta.get("status") or meta.get("message_status") or "").lower()


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _trace_end_time(trace: dict[str, Any]) -> datetime | None:
    """上一条结束时间：优先 end_time，否则 start_time + latency。"""
    end_dt = _parse_timestamp(trace.get("end_time"))
    if end_dt is not None:
        return end_dt
    start_dt = _parse_timestamp(trace.get("timestamp"))
    if start_dt is None:
        return None
    try:
        latency_s = float(trace.get("latency") or 0)
    except (TypeError, ValueError):
        latency_s = 0.0
    if latency_s < 0:
        latency_s = 0.0
    return start_dt + timedelta(seconds=latency_s)


class BatchEvalService:
    """批量评估编排服务。"""

    def __init__(
        self,
        *,
        llm_caller: LLMCaller,
        langfuse_client: Any | None = None,
    ) -> None:
        self.llm_caller = llm_caller
        self.langfuse = (
            langfuse_client if langfuse_client is not None else get_langfuse()
        )
        self.cfg = settings.eval_worker
        self.judge_input_builder = JudgeInputBuilder(langfuse_client=self.langfuse)

    def create_run_log(self, *, run_type: str = "scheduled") -> EvalRunLog:
        """创建一条 status=running 的评估运行日志并立即落库。"""
        now = get_datetime_now()
        run_log = EvalRunLog(run_type=run_type, started_at=now, status="running")
        with Session(engine) as db:
            db.add(run_log)
            db.commit()
            db.refresh(run_log)
            # Detach so callers can safely use the object after session close.
            return EvalRunLog.model_validate(run_log.model_dump())

    async def execute_run(
        self,
        run_id: str,
        *,
        hours: int | None = None,
        dry_run: bool = False,
    ) -> EvalRunLog:
        """执行已创建的评估运行并写回终态。"""
        with Session(engine) as db:
            run_log = db.get(EvalRunLog, run_id)
            if run_log is None:
                raise LookupError(f"eval run log not found: {run_id}")
            # Detach a working copy so in-memory counters can accumulate
            # outside the session before the final write-back.
            working = EvalRunLog.model_validate(run_log.model_dump())

        try:
            await self._do_run(working, hours=hours, dry_run=dry_run)
            working.status = "success"
        except Exception as exc:
            working.status = "failed"
            working.error_message = str(exc)[:2000]
            logger.error(
                "Batch eval failed",
                error=exc,
                error_type=type(exc).__name__,
            )

        working.finished_at = get_datetime_now()
        with Session(engine) as db:
            db_log = db.get(EvalRunLog, run_id)
            if db_log is not None:
                db_log.status = working.status
                db_log.finished_at = working.finished_at
                db_log.error_message = working.error_message
                db_log.total_traces = working.total_traces
                db_log.after_dedup = working.after_dedup
                db_log.candidate_pool = working.candidate_pool
                db_log.sampled_count = working.sampled_count
                db_log.sample_breakdown = working.sample_breakdown
                db_log.judge_success = working.judge_success
                db_log.judge_failed = working.judge_failed
                db_log.low_score_count = working.low_score_count
                db_log.score_summary = working.score_summary
                db.add(db_log)
                db.commit()
                db.refresh(db_log)
                working = db_log

        logger.info(
            "Batch eval finished",
            run_id=working.id,
            status=working.status,
            total_traces=working.total_traces,
            sampled=working.sampled_count,
            judge_success=working.judge_success,
            judge_failed=working.judge_failed,
            low_scores=working.low_score_count,
            dry_run=dry_run,
        )
        return working

    async def run(
        self,
        *,
        run_type: str = "scheduled",
        hours: int | None = None,
        dry_run: bool = False,
    ) -> EvalRunLog:
        """同步执行一次完整的批量评估（脚本 / worker 入口）。"""
        run_log = self.create_run_log(run_type=run_type)
        return await self.execute_run(run_log.id, hours=hours, dry_run=dry_run)

    async def _do_run(
        self,
        run_log: EvalRunLog,
        *,
        hours: int | None,
        dry_run: bool,
    ) -> None:
        lookback = hours if hours is not None else self.cfg.lookback_hours
        logger.info("Step 1: Fetching traces from Langfuse...", hours=lookback)
        traces = self._fetch_traces(hours=lookback)
        run_log.total_traces = len(traces)
        if not traces:
            logger.info("No traces to evaluate, exiting")
            return

        logger.info("Step 2: Completion gate + dedup...")
        traces = self._apply_completion_gate(traces)
        traces, thumb_down_ids, low_score_ids = self._dedup_with_bad_cases(traces)
        run_log.after_dedup = len(traces)
        if not traces:
            return

        logger.info("Step 3: Stratified sampling...")
        follow_ups = self._detect_follow_ups(traces)
        sample_result = stratified_sample(
            traces,
            follow_up_trace_ids=follow_ups,
            thumb_down_message_ids=thumb_down_ids,
            sample_rates=sample_rates_from_config(self.cfg),
            high_latency_threshold_s=self.cfg.high_latency_threshold_s,
        )
        run_log.candidate_pool = len(traces) - sample_result.skipped_rule_filter
        run_log.sampled_count = len(sample_result.traces)
        run_log.sample_breakdown = sample_result.breakdown

        if not sample_result.traces:
            logger.info("No traces sampled, exiting")
            return

        if dry_run:
            logger.info(
                "Dry-run: skip judge",
                sampled=run_log.sampled_count,
                breakdown=run_log.sample_breakdown,
            )
            return

        logger.info(
            "Step 4: Judge evaluation",
            count=len(sample_result.traces),
        )
        judge_results = await self._batch_judge(sample_result.traces)
        run_log.judge_success = sum(1 for _, r in judge_results if r.success)
        run_log.judge_failed = sum(1 for _, r in judge_results if not r.success)

        threshold = int(self.cfg.judge_low_score_threshold)
        run_log.score_summary = build_score_summary(
            judge_results,
            threshold_correctness=threshold,
            threshold_completeness=threshold,
            follow_up_trace_ids=follow_ups,
            thumb_down_message_ids=thumb_down_ids,
            high_latency_threshold_s=float(self.cfg.high_latency_threshold_s),
        )

        logger.info("Step 5: Writing scores and enqueueing low scores...")
        run_log.low_score_count = await self._write_results(
            judge_results,
            thumb_down_ids=thumb_down_ids,
            low_score_ids=low_score_ids,
        )

    def _fetch_traces(self, *, hours: int) -> list[dict[str, Any]]:
        """Langfuse v4: 用 observations(chat-turn) + scores(v3) 组装评估候选。"""
        if not self.langfuse:
            logger.warning("Langfuse client not available, cannot fetch traces")
            return []

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        try:
            observations = self._fetch_chat_turn_observations(since=since)
        except Exception as exc:
            logger.warning(
                "Failed to fetch chat-turn observations",
                error=exc,
                error_type=type(exc).__name__,
            )
            return []

        if not observations:
            return []

        try:
            scores_by_obs, scores_by_trace = self._fetch_scores_index(since=since)
        except Exception as exc:
            logger.warning(
                "Failed to fetch scores; continue without scores",
                error=exc,
                error_type=type(exc).__name__,
            )
            scores_by_obs, scores_by_trace = {}, {}

        traces: list[dict[str, Any]] = []
        for obs in observations:
            obs_id = str(obs.get("id") or "")
            trace_id = str(obs.get("trace_id") or "")
            scores = list(scores_by_obs.get(obs_id, []))
            if not scores and trace_id:
                scores = list[dict[str, Any]](scores_by_trace.get(trace_id, []))
            traces.append(self._observation_to_trace_dict(obs, scores))
        return traces

    def _fetch_chat_turn_observations(self, *, since: datetime) -> list[dict[str, Any]]:
        client = self.langfuse
        if client is None:
            raise RuntimeError("Langfuse client is not available")
        api = getattr(client, "api", None)
        observations_api = (
            getattr(api, "observations", None) if api is not None else None
        )
        if observations_api is None or not hasattr(observations_api, "get_many"):
            raise RuntimeError("Langfuse client missing observations API")

        all_obs: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "limit": TRACE_PAGE_SIZE,
                "from_start_time": since,
                "name": CHAT_TURN_OBSERVATION_NAME,
                "fields": "core,io,metadata",
            }
            if cursor:
                kwargs["cursor"] = cursor
            response = observations_api.get_many(**kwargs)
            data = getattr(response, "data", None) or []
            all_obs.extend(_trace_to_dict(item) for item in data)
            meta = getattr(response, "meta", None)
            next_cursor = None
            if meta is not None:
                if isinstance(meta, dict):
                    next_cursor = meta.get("cursor")
                else:
                    next_cursor = getattr(meta, "cursor", None)
            if not data or not next_cursor or len(data) < TRACE_PAGE_SIZE:
                break
            cursor = str(next_cursor)
        return all_obs

    def _fetch_scores_index(
        self, *, since: datetime
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        """拉取 scores 并按 observation_id / trace_id 建索引。"""
        cfg = settings.langfuse
        if not cfg.host or not cfg.public_key or not cfg.secret_key:
            return {}, {}

        by_obs: dict[str, list[dict[str, Any]]] = {}
        by_trace: dict[str, list[dict[str, Any]]] = {}
        url = f"{cfg.host.rstrip('/')}/api/public/v3/scores"
        cursor: str | None = None
        since_iso = since.isoformat().replace("+00:00", "Z")

        with httpx.Client(timeout=30.0, auth=(cfg.public_key, cfg.secret_key)) as http:
            while True:
                params: dict[str, Any] = {
                    "limit": TRACE_PAGE_SIZE,
                    "fromTimestamp": since_iso,
                    "fields": "subject",
                }
                if cursor:
                    params["cursor"] = cursor
                response = http.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("data") or []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get("name") or "")
                    score_item = {"name": name, "value": row.get("value")}
                    subject = row.get("subject") or {}
                    if isinstance(subject, dict):
                        obs_id = str(subject.get("id") or "")
                        trace_id = str(subject.get("traceId") or "")
                        if obs_id:
                            by_obs.setdefault(obs_id, []).append(score_item)
                        if trace_id:
                            by_trace.setdefault(trace_id, []).append(score_item)

                meta = payload.get("meta") or {}
                next_cursor = meta.get("cursor") if isinstance(meta, dict) else None
                if not rows or not next_cursor or len(rows) < TRACE_PAGE_SIZE:
                    break
                cursor = str(next_cursor)

        return by_obs, by_trace

    @staticmethod
    def _observation_to_trace_dict(
        obs: dict[str, Any], scores: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """把 observation 规范成 sampler / judge 使用的 trace-like dict。"""
        meta = obs.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        # 去掉 OTEL scope 噪音字段，保留业务 metadata
        clean_meta = {
            k: v
            for k, v in meta.items()
            if not str(k).startswith("scope.")
            and not str(k).startswith("resourceAttributes.")
        }
        return {
            "id": str(obs.get("trace_id") or obs.get("id") or ""),
            "observation_id": str(obs.get("id") or ""),
            "input": obs.get("input"),
            "output": obs.get("output"),
            "metadata": clean_meta,
            # observations API 常不带 session_id；埋点时 session_id=conversation_id
            "sessionId": obs.get("session_id") or clean_meta.get("conversation_id"),
            "userId": obs.get("user_id"),
            "latency": obs.get("latency") or 0,
            "timestamp": obs.get("start_time"),
            "end_time": obs.get("end_time"),
            "scores": scores,
        }

    def _apply_completion_gate(
        self, traces: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for t in traces:
            status = _trace_status(t)
            if status in TERMINAL_EXCLUDE_STATUSES:
                continue
            if not _has_valid_answer_score(t):
                continue
            kept.append(t)
        return kept

    def _dedup_with_bad_cases(
        self, traces: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        message_ids = {_message_id(t) for t in traces if _message_id(t)}
        thumb_down_ids: set[str] = set()
        low_score_ids: set[str] = set()
        thumb_down_without_judge: set[str] = set()

        if message_ids:
            with Session(engine) as db:
                message_id_column = cast(Any, BadCaseItemDb.message_id)
                rows = db.exec(
                    select(BadCaseItemDb).where(message_id_column.in_(message_ids))
                ).all()
                for row in rows:
                    mid = row.message_id or ""
                    if not mid:
                        continue
                    if row.source == BadCaseSource.LOW_SCORE.value:
                        low_score_ids.add(mid)
                    if row.source == BadCaseSource.THUMB_DOWN.value:
                        thumb_down_ids.add(mid)
                        has_judge = bool(
                            isinstance(row.judge_scores, dict) and row.judge_scores
                        )
                        if not has_judge:
                            thumb_down_without_judge.add(mid)

        deduped: list[dict[str, Any]] = []
        for t in traces:
            if _has_judge_scores(t):
                continue
            mid = _message_id(t)
            if mid and mid in low_score_ids:
                continue
            # thumb_down 无裁判分仍保留（100% 采样）
            deduped.append(t)

        # 仅把「尚无裁判分」的 thumb_down 交给 sampler 特殊桶
        return deduped, thumb_down_without_judge, low_score_ids

    def _detect_follow_ups(self, traces: list[dict[str, Any]]) -> set[str]:
        """检测快速追问：同一 session 内，下一条开始 − 上一条结束 ≤ 阈值。"""
        threshold = float(self.cfg.quick_follow_up_threshold_s)
        sessions: dict[str, list[dict[str, Any]]] = {}
        for t in traces:
            sid = str(t.get("sessionId") or t.get("session_id") or "").strip()
            # 无 session 无法判定同会话追问；归入 unknown 会把无关 turn 误判为 follow-up
            if not sid:
                continue
            sessions.setdefault(sid, []).append(t)

        follow_ups: set[str] = set()
        for session_traces in sessions.values():
            session_traces.sort(key=lambda item: str(item.get("timestamp") or ""))
            for i in range(1, len(session_traces)):
                prev = session_traces[i - 1]
                curr = session_traces[i]
                prev_end = _trace_end_time(prev)
                curr_start = _parse_timestamp(curr.get("timestamp"))
                if not prev_end or not curr_start:
                    continue
                # 用户看到上一条回复后多久又发下一条
                gap = (curr_start - prev_end).total_seconds()
                if 0 < gap <= threshold:
                    prev_id = str(prev.get("id") or "")
                    if prev_id:
                        follow_ups.add(prev_id)
        return follow_ups

    async def _batch_judge(
        self, traces: list[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], JudgeResult]]:
        semaphore = asyncio.Semaphore(self.cfg.judge_concurrency)
        timeout = float(self.cfg.judge_timeout_s)

        async def _judge_one(
            trace: dict[str, Any],
        ) -> tuple[dict[str, Any], JudgeResult]:
            async with semaphore:
                # Langfuse/DB I/O 为同步，放到线程池避免阻塞事件循环
                judge_input = await asyncio.to_thread(
                    self.judge_input_builder.build_from_trace, trace
                )
                try:
                    result = await asyncio.wait_for(
                        call_judge_model(
                            query=judge_input.query,
                            answer=judge_input.answer,
                            reference_contexts=judge_input.reference_xml,
                            llm_caller=self.llm_caller,
                            context_sources=judge_input.source_flags,
                        ),
                        timeout=timeout,
                    )
                except TimeoutError:
                    result = JudgeResult(
                        success=False,
                        error=f"judge timeout after {timeout}s",
                        context_sources=judge_input.source_flags,
                    )
                return trace, result

        return list(await asyncio.gather(*[_judge_one(t) for t in traces]))

    async def _write_results(
        self,
        results: list[tuple[dict[str, Any], JudgeResult]],
        *,
        thumb_down_ids: set[str],
        low_score_ids: set[str],
    ) -> int:
        _ = low_score_ids
        low_count = 0
        threshold = int(self.cfg.judge_low_score_threshold)

        with Session(engine) as db:
            bad_case_service = BadCaseService(db)

            for trace, judge_result in results:
                if not judge_result.success:
                    continue

                trace_id = str(trace.get("id") or "")
                meta = _metadata(trace)
                message_id = _message_id(trace)
                judge_scores = {
                    "correctness": judge_result.correctness,
                    "completeness": judge_result.completeness,
                    "notes": judge_result.notes,
                    "context_sources": judge_result.context_sources,
                }
                rule_scores = {
                    k: v
                    for k, v in _score_map(trace).items()
                    if not k.startswith(JUDGE_SCORE_PREFIX)
                }

                if self.langfuse and trace_id:
                    observation_id = str(trace.get("observation_id") or "") or None
                    try:
                        self.langfuse.create_score(
                            trace_id=trace_id,
                            observation_id=observation_id,
                            name="judge_correctness",
                            value=judge_result.correctness,
                            data_type="NUMERIC",
                        )
                        self.langfuse.create_score(
                            trace_id=trace_id,
                            observation_id=observation_id,
                            name="judge_completeness",
                            value=judge_result.completeness,
                            data_type="NUMERIC",
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to write Langfuse score",
                            trace_id=trace_id,
                            error=exc,
                        )

                if message_id and message_id in thumb_down_ids:
                    bad_case_service.update_judge_scores(
                        message_id=message_id,
                        source=BadCaseSource.THUMB_DOWN,
                        judge_scores=judge_scores,
                    )
                    continue

                min_score = min(judge_result.correctness, judge_result.completeness)
                if min_score < threshold:
                    low_count += 1
                    bad_case_service.enqueue(
                        source=BadCaseSource.LOW_SCORE,
                        message_id=message_id or None,
                        conversation_id=str(meta.get("conversation_id") or "") or None,
                        user_id=str(trace.get("userId") or "") or None,
                        query=_as_text(trace.get("input", ""))[:500],
                        answer=_as_text(trace.get("output", ""))[:1000],
                        rule_scores=rule_scores,
                        judge_scores=judge_scores,
                        trace_id=trace_id or None,
                    )

            db.commit()

        return low_count

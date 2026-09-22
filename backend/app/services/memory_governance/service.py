"""记忆治理编排：选人 → 按用户 fan-out 调 Mem0 Dream pass → 汇总运行报告。

选人口径（两层，主信号只有聊天活跃度）：
1. 日跑：``conversations.last_message_created_at`` 在窗口内 = 近期真实产生过记忆写入的用户。
2. 周扫：Mem0 全量记忆列表去重出的 user_id，覆盖「有记忆但近期无聊天」的沉睡用户。

不用 ``users.last_login_at``：那是会话续期时间（JWT 寿命 35 天，见 ``app/core/jwt.py``），
与「谁写了新记忆」不对齐，用它会让「一直在用旧 token 聊天」的活跃用户掉出治理窗口。

两道省钱闸门：水位去重（上次 pass ≥ 该用户最后一条消息时间 → 跳过）与最小记忆量
（低于 ``min_memories`` 直接跳过，为个位数记忆跑全量 consolidate/synthesis 不划算）。

调度入口见 ``memory_worker/main.py``；这里只负责「选人 + 调用 + 汇总」，不落库
（每次 pass 的审计由 Mem0 侧的 ``dream_passes`` / ``dream_actions`` 承担）。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

import httpx
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.conversation_db import ConversationDb
from app.schemas.config import MemoryConfig, MemoryGovernanceWorkerConfig
from app.services.memory_governance.dream_client import (
    DreamBackendUnsupported,
    DreamClient,
    DreamPassError,
)
from app.utils.date import get_datetime_now
from app.utils.logger import logger

RunMode = Literal["daily", "sweep"]


class GovernanceClient(Protocol):
    """治理所需的 Mem0 能力约定（便于用替身测试编排逻辑）。"""

    def enabled(self) -> bool: ...

    def is_platform(self) -> bool: ...

    async def run_pass(
        self,
        *,
        user_id: str,
        consolidate: bool = True,
        synthesize: bool = True,
        force: bool = False,
    ) -> dict[str, Any]: ...

    async def last_full_pass_at(self, user_id: str) -> datetime | None: ...

    async def memory_count(self, user_id: str) -> int | None: ...

    async def list_memory_user_ids(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 50,
        max_users: int | None = None,
    ) -> list[str]: ...


@dataclass
class UserActivity:
    """一个待治理对象：``last_active_at`` 为该用户最后一条消息时间。

    周扫发现的用户没有可靠的「最后活动时间」→ 传 ``None``，水位退化为按
    ``min_pass_interval_days`` 的固定间隔判断。
    """

    user_id: str
    last_active_at: datetime | None = None
    source: Literal["chat", "sweep"] = "chat"


@dataclass
class UserDreamOutcome:
    """单个用户的治理结果。"""

    user_id: str
    status: str  # ok | skipped | failed
    attempts: int = 0
    duration_ms: int = 0
    pass_id: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "user_id": self.user_id,
            "status": self.status,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
        }
        if self.pass_id is not None:
            result["pass_id"] = self.pass_id
        if self.stats:
            result["stats"] = self.stats
        if self.reason is not None:
            result["reason"] = self.reason
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class DreamRunReport:
    """一次记忆治理运行的汇总。"""

    started_at: datetime
    mode: RunMode = "daily"
    finished_at: datetime | None = None
    scanned_users: int = 0
    outcomes: list[UserDreamOutcome] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "ok")

    @property
    def skipped(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "skipped")

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "failed")

    @property
    def duration_ms(self) -> int:
        if self.finished_at is None:
            return 0
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    def finish(self) -> DreamRunReport:
        self.finished_at = get_datetime_now()
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "scanned_users": self.scanned_users,
            "succeeded": self.succeeded,
            "skipped": self.skipped,
            "failed": self.failed,
            "failures": [o.to_dict() for o in self.outcomes if o.status == "failed"],
        }


def select_chat_active_users(
    session: Session,
    config: MemoryGovernanceWorkerConfig,
) -> list[UserActivity]:
    """按聊天活跃度选人：近 ``activity_within_days`` 天有对话消息的用户。

    走 ``ix_conversations_user_active_last_msg``（``user_id`` + ``last_message_created_at``）；
    对话消息会触发记忆写入（``app/services/chat/post_process_service.py``），因此这个口径
    与「谁产生了新记忆」直接对齐。不用 ``users.last_login_at``（会话续期时间，且
    ``UserDb.status`` 登出即 ``inactive``，都不能当活跃判据）。
    """
    last_message = func.max(ConversationDb.last_message_created_at)
    stmt = (
        select(ConversationDb.user_id, last_message)
        .where(ConversationDb.user_id.is_not(None))  # type: ignore[union-attr]
        .group_by(ConversationDb.user_id)
    )
    if config.activity_within_days > 0:
        cutoff = get_datetime_now() - timedelta(days=config.activity_within_days)
        stmt = stmt.having(last_message >= cutoff)
    stmt = stmt.order_by(desc(last_message)).limit(config.max_users_per_run)
    rows = session.exec(stmt).all()
    return [
        UserActivity(user_id=str(row[0]), last_active_at=row[1], source="chat")
        for row in rows
        if row[0]
    ]


class MemoryGovernanceService:
    """一次记忆治理运行的编排器。

    依赖均可注入，便于测试：``client``（Mem0 调用）、``session_factory``（选人）、
    ``sleep``（重试退避）。
    """

    def __init__(
        self,
        *,
        worker_config: MemoryGovernanceWorkerConfig | None = None,
        memory_config: MemoryConfig | None = None,
        client: GovernanceClient | None = None,
        session_factory: Callable[[], Session] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.config = worker_config or settings.memory_governance_worker
        memory_config = memory_config or settings.chat_context.memory_config
        self._client = client or DreamClient(
            memory_config, timeout_s=self.config.request_timeout_s
        )
        self._session_factory = session_factory or (lambda: Session(engine))
        self._sleep = sleep

    def collect_user_ids(self) -> list[UserActivity]:
        with self._session_factory() as session:
            return select_chat_active_users(session, self.config)

    async def collect_sweep_users(self) -> list[UserActivity]:
        """周扫目标：Mem0 全量记忆列表里出现过的 user_id（去重）。

        admin 列表被拒（403）或后端不支持时只记日志并返回空列表——周扫是长尾补漏，
        不应该让整个 Worker 失败。
        """
        try:
            user_ids = await self._client.list_memory_user_ids(
                page_size=self.config.sweep_page_size,
                max_pages=self.config.sweep_max_pages,
                max_users=self.config.max_users_per_run,
            )
        except DreamBackendUnsupported as e:
            logger.warning("Memory governance sweep unsupported", error=e)
            return []
        except (DreamPassError, httpx.HTTPError) as e:
            logger.error("Memory governance sweep discovery failed", error=e)
            return []
        return [
            UserActivity(user_id=uid, last_active_at=None, source="sweep")
            for uid in user_ids
        ]

    async def run(
        self,
        *,
        users: Sequence[UserActivity] | None = None,
        mode: RunMode = "daily",
    ) -> DreamRunReport:
        """执行一次治理运行。

        ``users`` 为 ``None`` 时：``mode="daily"`` 按配置从库里选人，
        ``mode="sweep"`` 从 Mem0 全量记忆列表发现候选用户。
        """
        report = DreamRunReport(started_at=get_datetime_now(), mode=mode)
        if not self.config.enabled:
            logger.info("Memory governance worker disabled, skip run", mode=mode)
            return report.finish()
        if not self._client.enabled():
            logger.error(
                "memory_config.base_url / api_key 未配置，跳过记忆治理", mode=mode
            )
            return report.finish()
        if self._client.is_platform():
            logger.error(
                "Mem0 Platform 不支持外部触发 Dream pass，跳过记忆治理", mode=mode
            )
            return report.finish()

        if users is not None:
            targets = list(users)
        elif mode == "sweep":
            targets = await self.collect_sweep_users()
        else:
            targets = self.collect_user_ids()

        report.scanned_users = len(targets)
        if not targets:
            logger.info("Memory governance run: no target users", mode=mode)
            return report.finish()

        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def _one(activity: UserActivity) -> UserDreamOutcome:
            async with semaphore:
                return await self._govern_user(activity)

        report.outcomes = list(await asyncio.gather(*(_one(a) for a in targets)))
        report.finish()
        logger.info(
            "Memory governance run finished",
            mode=mode,
            scanned_users=report.scanned_users,
            succeeded=report.succeeded,
            skipped=report.skipped,
            failed=report.failed,
            duration_ms=report.duration_ms,
        )
        return report

    async def _skip_reason(self, activity: UserActivity) -> str | None:
        """两道省钱闸门：水位去重 + 最小记忆量。返回跳过原因，``None`` 表示可治理。

        水位只看**全量** pass（``source != "on_add"``）：写记忆触发的 on_add
        consolidate 只做 merge/supersede，不代表 synthesis 已跑过。
        """
        user_id = activity.user_id
        if self.config.skip_if_governed:
            last_pass = await self._client.last_full_pass_at(user_id)
            if last_pass is not None:
                if activity.last_active_at is not None:
                    if last_pass >= activity.last_active_at:
                        return "governed_after_last_message"
                elif self.config.min_pass_interval_days > 0:
                    floor = get_datetime_now() - timedelta(
                        days=self.config.min_pass_interval_days
                    )
                    if last_pass >= floor:
                        return "governed_within_min_interval"
        if self.config.min_memories > 0:
            count = await self._client.memory_count(user_id)
            if count is not None and count < self.config.min_memories:
                return f"below_min_memories:{count}<{self.config.min_memories}"
        return None

    async def _govern_user(self, activity: UserActivity) -> UserDreamOutcome:
        user_id = activity.user_id
        outcome = UserDreamOutcome(user_id=user_id, status="failed")
        started = time.perf_counter()
        try:
            reason = await self._skip_reason(activity)
        except DreamBackendUnsupported as e:
            # 配置/后端能力问题，重试无意义
            outcome.error = str(e)
            outcome.reason = "unsupported_backend"
            outcome.duration_ms = int((time.perf_counter() - started) * 1000)
            logger.error("Dream pass unsupported", user_id=user_id, error=e)
            return outcome
        if reason is not None:
            outcome.status = "skipped"
            outcome.reason = reason
            outcome.duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info("Memory governance skipped", user_id=user_id, reason=reason)
            return outcome

        last_error: str | None = None
        for attempt in range(1, self.config.retry_attempts + 1):
            outcome.attempts = attempt
            try:
                dream_report = await self._client.run_pass(
                    user_id=user_id,
                    consolidate=self.config.consolidate,
                    synthesize=self.config.synthesize,
                    force=self.config.force,
                )
            except DreamBackendUnsupported as e:
                # 配置/后端能力问题，重试无意义
                last_error = str(e)
                logger.error("Dream pass unsupported", user_id=user_id, error=e)
                break
            except (DreamPassError, httpx.HTTPError) as e:
                last_error = str(e)
                logger.warning(
                    "Dream pass attempt failed",
                    user_id=user_id,
                    attempt=attempt,
                    error=e,
                )
                if attempt < self.config.retry_attempts:
                    await self._sleep(self.config.retry_backoff_s * 2 ** (attempt - 1))
                continue

            outcome.status = "ok"
            outcome.pass_id = dream_report.get("pass_id")
            stats = dream_report.get("stats")
            outcome.stats = stats if isinstance(stats, dict) else {}
            last_error = None
            break

        outcome.error = last_error
        outcome.duration_ms = int((time.perf_counter() - started) * 1000)
        return outcome

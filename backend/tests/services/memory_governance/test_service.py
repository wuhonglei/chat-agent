"""MemoryGovernanceService：选人（聊天/登录口径）、fan-out、闸门、失败隔离与重试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine
from sqlmodel import Session

from app.models.conversation_db import ConversationDb
from app.models.user import UserDb
from app.schemas.config import MemoryConfig, MemoryGovernanceWorkerConfig
from app.services.memory_governance.dream_client import (
    DreamBackendUnsupported,
    DreamPassError,
)
from app.services.memory_governance.service import (
    MemoryGovernanceService,
    UserActivity,
    select_chat_active_users,
)
from app.utils.cron import parse_cron_5field


class FakeGovernanceClient:
    """可脚本化的 GovernanceClient 替身：按 user_id 返回成功 / 异常 / 读数。"""

    def __init__(
        self,
        *,
        fail_sequence: dict[str, list[Exception]] | None = None,
        last_pass: dict[str, datetime | None] | None = None,
        memory_counts: dict[str, int | None] | None = None,
        memory_user_ids: list[str] | None = None,
        sweep_error: Exception | None = None,
        platform: bool = False,
        enabled: bool = True,
    ) -> None:
        self._fail_sequence = {k: list(v) for k, v in (fail_sequence or {}).items()}
        self._last_pass = dict(last_pass or {})
        self._memory_counts = dict(memory_counts or {})
        self._memory_user_ids = list(memory_user_ids or [])
        self._sweep_error = sweep_error
        self._platform = platform
        self._enabled = enabled
        self.calls: list[dict[str, Any]] = []
        self.sweep_calls = 0

    def enabled(self) -> bool:
        return self._enabled

    def is_platform(self) -> bool:
        return self._platform

    async def run_pass(
        self,
        *,
        user_id: str,
        consolidate: bool = True,
        synthesize: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "user_id": user_id,
                "consolidate": consolidate,
                "synthesize": synthesize,
                "force": force,
            }
        )
        pending = self._fail_sequence.get(user_id)
        if pending:
            raise pending.pop(0)
        return {"pass_id": f"pass-{user_id}", "stats": {"merged": 1}}

    async def last_full_pass_at(self, user_id: str) -> datetime | None:
        return self._last_pass.get(user_id)

    async def memory_count(self, user_id: str) -> int | None:
        return self._memory_counts.get(user_id)

    async def list_memory_user_ids(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 50,
        max_users: int | None = None,
    ) -> list[str]:
        self.sweep_calls += 1
        if self._sweep_error is not None:
            raise self._sweep_error
        return list(self._memory_user_ids)


def _worker_config(**overrides: Any) -> MemoryGovernanceWorkerConfig:
    base: dict[str, Any] = {
        "enabled": True,
        "concurrency": 2,
        "retry_attempts": 3,
        "retry_backoff_s": 1.0,
        "synthesize": True,
        "consolidate": True,
        "force": False,
        "min_memories": 0,
        "skip_if_governed": False,
    }
    base.update(overrides)
    return MemoryGovernanceWorkerConfig(**base)


def _activity(user_id: str, days_ago: float = 1.0) -> UserActivity:
    return UserActivity(
        user_id=user_id,
        last_active_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        source="chat",
    )


@pytest.mark.asyncio
async def test_run_aggregates_successful_users() -> None:
    client = FakeGovernanceClient()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    service = MemoryGovernanceService(
        worker_config=_worker_config(), client=client, sleep=fake_sleep
    )
    report = await service.run(users=[_activity("u1"), _activity("u2")])

    assert report.mode == "daily"
    assert report.scanned_users == 2
    assert report.succeeded == 2
    assert report.skipped == 0
    assert report.failed == 0
    assert report.finished_at is not None
    outcomes = {o.user_id: o for o in report.outcomes}
    assert outcomes["u1"].pass_id == "pass-u1"
    assert outcomes["u1"].stats == {"merged": 1}
    assert outcomes["u1"].status == "ok"
    assert sleeps == []
    assert {c["user_id"] for c in client.calls} == {"u1", "u2"}
    assert report.to_dict()["failures"] == []


@pytest.mark.asyncio
async def test_run_retries_then_succeeds_and_isolates_failures() -> None:
    client = FakeGovernanceClient(
        fail_sequence={
            # u1: 前两次失败，第三次成功
            "u1": [DreamPassError(502, "boom"), DreamPassError(502, "boom")],
            # u2: 三次都失败
            "u2": [
                DreamPassError(500, "down"),
                DreamPassError(500, "down"),
                DreamPassError(500, "down"),
            ],
            # u3: 后端能力不支持，直接放弃不再重试
            "u3": [DreamBackendUnsupported("not supported")],
        }
    )
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    service = MemoryGovernanceService(
        worker_config=_worker_config(), client=client, sleep=fake_sleep
    )
    report = await service.run(
        users=[_activity("u1"), _activity("u2"), _activity("u3")]
    )
    outcomes = {o.user_id: o for o in report.outcomes}

    assert outcomes["u1"].status == "ok"
    assert outcomes["u1"].attempts == 3
    assert outcomes["u2"].status == "failed"
    assert outcomes["u2"].attempts == 3
    assert outcomes["u2"].error is not None
    assert outcomes["u3"].status == "failed"
    assert outcomes["u3"].attempts == 1
    assert report.succeeded == 1
    assert report.failed == 2
    # 退避：u1 两次(1s,2s) + u2 两次(1s,2s)，u3 不重试
    assert sorted(sleeps) == [1.0, 1.0, 2.0, 2.0]
    assert len(report.to_dict()["failures"]) == 2
    assert len(client.calls) == 7


@pytest.mark.asyncio
async def test_run_skips_when_disabled_or_platform() -> None:
    disabled = MemoryGovernanceService(
        worker_config=_worker_config(enabled=False), client=FakeGovernanceClient()
    )
    report = await disabled.run(users=[_activity("u1")])
    assert report.scanned_users == 0
    assert report.outcomes == []

    platform = MemoryGovernanceService(
        worker_config=_worker_config(), client=FakeGovernanceClient(platform=True)
    )
    report = await platform.run(users=[_activity("u1")])
    assert report.scanned_users == 0
    assert report.outcomes == []

    unconfigured = MemoryGovernanceService(
        worker_config=_worker_config(),
        memory_config=MemoryConfig(base_url="", api_key=""),
    )
    report = await unconfigured.run(users=[_activity("u1")])
    assert report.outcomes == []


@pytest.mark.asyncio
async def test_watermark_skips_users_without_new_activity() -> None:
    """水位：上次 pass 不早于最后一条消息 → 跳过，不再付费跑 pass。"""
    now = datetime.now(timezone.utc)
    client = FakeGovernanceClient(
        last_pass={
            "fresh": now - timedelta(hours=1),  # pass 晚于最后一条消息（1 天前）→ 跳过
            "stale": now - timedelta(days=5),  # pass 早于最后一条消息 → 照跑
        }
    )
    service = MemoryGovernanceService(
        worker_config=_worker_config(skip_if_governed=True), client=client
    )
    report = await service.run(
        users=[_activity("fresh", days_ago=1.0), _activity("stale", days_ago=1.0)]
    )
    outcomes = {o.user_id: o for o in report.outcomes}

    assert outcomes["fresh"].status == "skipped"
    assert outcomes["fresh"].reason == "governed_after_last_message"
    assert outcomes["stale"].status == "ok"
    assert report.skipped == 1
    assert report.succeeded == 1
    assert [c["user_id"] for c in client.calls] == ["stale"]


@pytest.mark.asyncio
async def test_sweep_users_use_min_pass_interval_floor() -> None:
    """周扫用户没有可靠的最后活动时间 → 用 min_pass_interval_days 兜底。"""
    now = datetime.now(timezone.utc)
    client = FakeGovernanceClient(
        last_pass={
            "recently": now - timedelta(days=2),  # 3 天间隔内 → 跳过
            "long_ago": now - timedelta(days=30),  # 超过间隔 → 照跑
        }
    )
    service = MemoryGovernanceService(
        worker_config=_worker_config(skip_if_governed=True, min_pass_interval_days=3),
        client=client,
    )
    report = await service.run(
        users=[
            UserActivity(user_id="recently", last_active_at=None, source="sweep"),
            UserActivity(user_id="long_ago", last_active_at=None, source="sweep"),
        ]
    )
    outcomes = {o.user_id: o for o in report.outcomes}
    assert outcomes["recently"].reason == "governed_within_min_interval"
    assert outcomes["long_ago"].status == "ok"


@pytest.mark.asyncio
async def test_min_memories_gate_skips_small_users() -> None:
    client = FakeGovernanceClient(memory_counts={"tiny": 3, "big": 42, "unknown": None})
    service = MemoryGovernanceService(
        worker_config=_worker_config(min_memories=10), client=client
    )
    report = await service.run(
        users=[_activity("tiny"), _activity("big"), _activity("unknown")]
    )
    outcomes = {o.user_id: o for o in report.outcomes}

    assert outcomes["tiny"].status == "skipped"
    assert outcomes["tiny"].reason == "below_min_memories:3<10"
    assert outcomes["big"].status == "ok"
    # 读数拿不到（None）时不拦截，避免误伤
    assert outcomes["unknown"].status == "ok"
    assert [c["user_id"] for c in client.calls] == ["big", "unknown"]


@pytest.mark.asyncio
async def test_sweep_mode_discovers_users_from_mem0() -> None:
    client = FakeGovernanceClient(memory_user_ids=["s1", "s2", "s1"])
    service = MemoryGovernanceService(
        worker_config=_worker_config(skip_if_governed=False), client=client
    )
    report = await service.run(mode="sweep")

    assert client.sweep_calls == 1
    assert report.mode == "sweep"
    assert report.scanned_users == 3  # 去重前由 client 负责，这里保持入参顺序
    assert report.succeeded == 3


@pytest.mark.asyncio
async def test_sweep_discovery_failure_is_not_fatal() -> None:
    client = FakeGovernanceClient(sweep_error=DreamPassError(403, "admin required"))
    service = MemoryGovernanceService(
        worker_config=_worker_config(skip_if_governed=False), client=client
    )
    report = await service.run(mode="sweep")

    assert report.scanned_users == 0
    assert report.outcomes == []
    assert client.calls == []


def test_worker_config_defaults() -> None:
    """默认值有回归兜底：被误改会立刻暴露（enabled / cron / 口径都是行为开关）。"""
    cfg = MemoryGovernanceWorkerConfig()
    assert cfg.enabled is True
    assert cfg.schedule_cron == "0 4 * * *"
    assert cfg.sweep_enabled is True
    assert cfg.sweep_cron == "0 4 * * sun"  # 用 sun 而非 0：APScheduler 里 0=周一
    # 选人口径只有聊天活跃度一种，不再保留 activity_source 开关
    assert "activity_source" not in MemoryGovernanceWorkerConfig.model_fields
    assert cfg.activity_within_days == 30
    assert cfg.min_memories == 10
    assert cfg.skip_if_governed is True
    assert cfg.min_pass_interval_days == 7
    assert cfg.run_on_startup is False

    now = datetime(2026, 1, 1, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    daily = CronTrigger(
        **parse_cron_5field(cfg.schedule_cron), timezone="Asia/Shanghai"
    ).get_next_fire_time(None, now)
    weekly = CronTrigger(
        **parse_cron_5field(cfg.sweep_cron), timezone="Asia/Shanghai"
    ).get_next_fire_time(None, now)
    assert daily is not None and (daily.hour, daily.minute) == (4, 0)
    assert weekly is not None and (weekly.hour, weekly.minute) == (4, 0)
    assert weekly.weekday() == 6  # 周日


def _seed_sqlite() -> tuple[Any, datetime]:
    engine = create_engine("sqlite://")
    UserDb.__table__.create(engine)  # type: ignore[attr-defined]
    ConversationDb.__table__.create(engine)  # type: ignore[attr-defined]
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add_all(
            [
                # 40 天没登录、但一直在聊天 → 必须入选（登录时间不是信号）
                UserDb(
                    id="chatty_no_relogin",
                    name="chatty",
                    status="active",
                    last_login_at=now - timedelta(days=40),
                ),
                # 刚登录但没有任何对话 → 不应入选；status 也只是登录会话标志（已登出）
                UserDb(
                    id="login_only",
                    name="login_only",
                    status="inactive",
                    last_login_at=now - timedelta(hours=2),
                ),
                UserDb(id="never_seen", name="never", status="active"),
            ]
        )
        session.add_all(
            [
                # 今天一直在聊（记忆在持续写入）
                ConversationDb(
                    id="c1",
                    title="t1",
                    user_id="chatty_no_relogin",
                    last_message_created_at=now - timedelta(hours=1),
                ),
                ConversationDb(
                    id="c2",
                    title="t2",
                    user_id="chatty_no_relogin",
                    last_message_created_at=now - timedelta(days=2),
                ),
                # 90 天没聊过
                ConversationDb(
                    id="c3",
                    title="t3",
                    user_id="dormant",
                    last_message_created_at=now - timedelta(days=90),
                ),
            ]
        )
        session.commit()
    return engine, now


def test_select_chat_active_users_wins_over_login_recency() -> None:
    """主口径：聊天活跃。40 天没登录但一直在聊的用户必须入选；只登录不聊天的不入选。"""
    engine, _ = _seed_sqlite()
    with Session(engine) as session:
        users = select_chat_active_users(
            session, _worker_config(activity_within_days=30, max_users_per_run=10)
        )
        assert [u.user_id for u in users] == ["chatty_no_relogin"]
        assert users[0].source == "chat"
        assert users[0].last_active_at is not None

        # 不设窗口 → 所有出现过的用户，按最后消息时间倒序
        all_users = select_chat_active_users(
            session, _worker_config(activity_within_days=0, max_users_per_run=10)
        )
        assert [u.user_id for u in all_users] == ["chatty_no_relogin", "dormant"]

        limited = select_chat_active_users(
            session, _worker_config(activity_within_days=0, max_users_per_run=1)
        )
        assert [u.user_id for u in limited] == ["chatty_no_relogin"]


def test_chat_selection_ignores_login_recency() -> None:
    """只按聊天活跃度选人：登录时间既不作为入选条件，也不参与排序。

    - `chatty_no_relogin`：40 天没登录、但今天还在聊 → 必须入选
    - `login_only`：2 小时前刚登录、但没有任何对话 → 不入选
    - `never_seen`：从未登录、没对话 → 不入选
    """
    engine, _ = _seed_sqlite()
    with Session(engine) as session:
        selected = select_chat_active_users(
            session, _worker_config(activity_within_days=30)
        )
        assert [u.user_id for u in selected] == ["chatty_no_relogin"]
        assert selected[0].source == "chat"

        nobody_by_login = select_chat_active_users(
            session, _worker_config(activity_within_days=1)
        )
        assert [u.user_id for u in nobody_by_login] == ["chatty_no_relogin"]

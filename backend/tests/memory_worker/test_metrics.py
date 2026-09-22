"""memory_worker 指标：report → 指标映射，以及 service 三层「整轮跳过」原因的打标。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from app.core.worker_metrics import WorkerMetrics
from app.schemas.config import MemoryConfig, MemoryGovernanceWorkerConfig
from app.services.memory_governance.service import (
    DreamRunReport,
    MemoryGovernanceService,
    UserDreamOutcome,
)
from memory_worker import metrics


def _no_db() -> Any:
    raise AssertionError("整轮跳过时不应该访问数据库")


class StubClient:
    """最小 GovernanceClient 替身：只回答「能不能治理」这几个问题。"""

    def __init__(self, *, enabled: bool = True, platform: bool = False) -> None:
        self._enabled = enabled
        self._platform = platform

    def enabled(self) -> bool:
        return self._enabled

    def is_platform(self) -> bool:
        return self._platform

    async def run_pass(self, **kwargs: Any) -> dict[str, Any]:
        return {"pass_id": "p1", "stats": {}}

    async def last_full_pass_at(self, user_id: str) -> datetime | None:
        return None

    async def memory_count(self, user_id: str) -> int | None:
        return 100

    async def list_memory_user_ids(self, **kwargs: Any) -> list[str]:
        return []


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """每个用例换一份干净 registry，避免计数器跨用例累加。"""
    fresh = WorkerMetrics(metrics.PREFIX, registry=CollectorRegistry())
    monkeypatch.setattr(metrics, "METRICS", fresh)
    monkeypatch.setattr(
        metrics,
        "SWEEP_ENABLED",
        Gauge(
            "memory_governance_sweep_enabled",
            "1 if the weekly sweep is enabled by configuration, 0 otherwise",
            registry=fresh.registry,
        ),
    )
    yield


def _value(name: str, labels: str = "") -> float:
    for line in generate_latest(metrics.METRICS.registry).decode().splitlines():
        if line.startswith(f"{name}{labels} "):
            return float(line.split(" ")[1])
    return -1.0


def _service(**kwargs: Any) -> MemoryGovernanceService:
    return MemoryGovernanceService(
        worker_config=kwargs.pop("worker_config", MemoryGovernanceWorkerConfig()),
        memory_config=MemoryConfig(base_url="http://mem0.test", api_key="k"),
        client=kwargs.pop("client", StubClient()),
        session_factory=kwargs.pop("session_factory", _no_db),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_report_maps_units_and_advances_heartbeat() -> None:
    report = DreamRunReport(started_at=datetime.now())
    report.scanned_users = 3
    report.outcomes = [
        UserDreamOutcome(user_id="u1", status="ok"),
        UserDreamOutcome(user_id="u2", status="ok"),
        UserDreamOutcome(user_id="u3", status="skipped", reason="governed"),
    ]

    metrics.record_report(report, duration_s=2.0)

    assert _value("memory_governance_runs_total", '{mode="daily",result="ok"}') == 1
    assert (
        _value("memory_governance_units_total", '{mode="daily",outcome="scanned"}') == 3
    )
    assert (
        _value("memory_governance_units_total", '{mode="daily",outcome="succeeded"}')
        == 2
    )
    assert (
        _value("memory_governance_units_total", '{mode="daily",outcome="skipped"}') == 1
    )
    assert (
        _value("memory_governance_last_success_timestamp_seconds", '{mode="daily"}') > 0
    )


@pytest.mark.asyncio
async def test_disabled_run_is_not_healthy() -> None:
    service = _service(worker_config=MemoryGovernanceWorkerConfig(enabled=False))
    report = await service.run(mode="daily")
    assert report.skip_reason == "disabled"

    metrics.record_report(report, duration_s=0.1)

    assert (
        _value("memory_governance_runs_total", '{mode="daily",result="disabled"}') == 1
    )
    # 心跳没被推进：staleness 告警需要靠 memory_governance_enabled==0 抑制
    assert (
        _value("memory_governance_last_success_timestamp_seconds", '{mode="daily"}')
        == -1
    )


@pytest.mark.asyncio
async def test_unconfigured_and_platform_are_labelled() -> None:
    for enabled, platform, reason, result in (
        (False, False, "not_configured", "not_configured"),
        (True, True, "platform", "unsupported"),
    ):
        service = _service(client=StubClient(enabled=enabled, platform=platform))
        report = await service.run(mode="daily")
        assert report.skip_reason == reason
        metrics.record_report(report, duration_s=0.1)
        assert (
            _value(
                "memory_governance_runs_total", f'{{mode="daily",result="{result}"}}'
            )
            == 1
        )


@pytest.mark.asyncio
async def test_run_with_no_candidates_is_ok_not_skipped() -> None:
    service = _service()
    report = await service.run(mode="daily", users=[])
    assert report.skip_reason is None

    metrics.record_report(report, duration_s=0.1)

    assert _value("memory_governance_runs_total", '{mode="daily",result="ok"}') == 1
    assert (
        _value("memory_governance_last_success_timestamp_seconds", '{mode="daily"}') > 0
    )


def test_failure_and_flags() -> None:
    metrics.set_flags(enabled=True, sweep_enabled=False)
    assert _value("memory_governance_enabled") == 1
    assert _value("memory_governance_sweep_enabled") == 0

    metrics.record_failure("sweep", duration_s=0.5)
    assert _value("memory_governance_run_duration_seconds", '{mode="sweep"}') == 0.5
    metrics.record_result("sweep", "disabled")

    assert _value("memory_governance_runs_total", '{mode="sweep",result="failed"}') == 1
    assert (
        _value("memory_governance_runs_total", '{mode="sweep",result="disabled"}') == 1
    )
    assert (
        _value("memory_governance_last_success_timestamp_seconds", '{mode="sweep"}')
        == -1
    )


def test_mark_process_start_covers_both_modes() -> None:
    metrics.mark_process_start()
    for mode in ("daily", "sweep"):
        # 新部署的宽限期：心跳先等于进程启动时间，而不是 0
        assert (
            _value(
                "memory_governance_last_success_timestamp_seconds", f'{{mode="{mode}"}}'
            )
            > 0
        )


def test_start_server_disabled_by_port_zero() -> None:
    assert metrics.start_server(0) is False

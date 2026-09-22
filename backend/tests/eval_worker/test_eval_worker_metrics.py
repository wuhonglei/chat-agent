"""eval_worker 指标：EvalRunLog → 指标映射与心跳语义。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from app.core.worker_metrics import WorkerMetrics
from app.models.eval_run_log_db import EvalRunLog
from app.utils.date import get_datetime_now
from eval_worker import metrics


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    fresh = WorkerMetrics(metrics.PREFIX, registry=CollectorRegistry())
    monkeypatch.setattr(metrics, "METRICS", fresh)
    yield


def _value(name: str, labels: str = "") -> float:
    for line in generate_latest(metrics.METRICS.registry).decode().splitlines():
        if line.startswith(f"{name}{labels} "):
            return float(line.split(" ")[1])
    return -1.0


def _run_log(*, status: str) -> EvalRunLog:
    return EvalRunLog(
        run_type="scheduled",
        started_at=get_datetime_now(),
        status=status,
        total_traces=120,
        after_dedup=100,
        candidate_pool=80,
        sampled_count=30,
        judge_success=28,
        judge_failed=2,
        low_score_count=3,
    )


def test_successful_run_records_units_and_heartbeat() -> None:
    metrics.record_run_log(_run_log(status="success"), duration_s=42.0)

    assert _value("evaluator_runs_total", '{mode="scheduled",result="ok"}') == 1
    assert _value("evaluator_run_duration_seconds", '{mode="scheduled"}') == 42.0
    assert _value("evaluator_units_total", '{mode="scheduled",outcome="traces"}') == 120
    assert _value("evaluator_units_total", '{mode="scheduled",outcome="sampled"}') == 30
    assert (
        _value("evaluator_units_total", '{mode="scheduled",outcome="judge_success"}')
        == 28
    )
    assert (
        _value("evaluator_units_total", '{mode="scheduled",outcome="low_score"}') == 3
    )
    assert _value("evaluator_last_success_timestamp_seconds", '{mode="scheduled"}') > 0


def test_failed_run_does_not_advance_heartbeat() -> None:
    metrics.record_run_log(_run_log(status="failed"), duration_s=5.0)

    assert _value("evaluator_runs_total", '{mode="scheduled",result="failed"}') == 1
    assert (
        _value("evaluator_last_success_timestamp_seconds", '{mode="scheduled"}') == -1
    )


def test_disabled_and_flags() -> None:
    metrics.set_flags(enabled=False)
    assert _value("evaluator_enabled") == 0

    metrics.record_result("disabled")

    assert _value("evaluator_runs_total", '{mode="scheduled",result="disabled"}') == 1


def test_raised_run_is_counted_as_failure() -> None:
    metrics.record_failure(duration_s=1.0)

    assert _value("evaluator_runs_total", '{mode="scheduled",result="failed"}') == 1
    assert (
        _value("evaluator_last_success_timestamp_seconds", '{mode="scheduled"}') == -1
    )


def test_mark_process_start_sets_grace_period() -> None:
    metrics.mark_process_start()
    assert _value("evaluator_last_success_timestamp_seconds", '{mode="scheduled"}') > 0

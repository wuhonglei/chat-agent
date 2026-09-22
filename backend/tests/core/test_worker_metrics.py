"""WorkerMetrics：运行结果打标、心跳语义、指标暴露与 HTTP 监听。"""

from __future__ import annotations

import socket
import time
import urllib.request

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from app.core.worker_metrics import WorkerMetrics, start_metrics_server


def _fresh() -> WorkerMetrics:
    return WorkerMetrics("demo_worker", registry=CollectorRegistry())


def _value(metrics: WorkerMetrics, name: str, labels: str = "") -> float:
    """从 exposition 文本里取一条样本的值，找不到返回 -1。"""
    text = generate_latest(metrics.registry).decode()
    target = f"{name}{labels}"
    for line in text.splitlines():
        if line.startswith(target + " "):
            return float(line.split(" ")[1])
    return -1.0


def test_ok_run_advances_heartbeat_and_counts_units() -> None:
    m = _fresh()
    before = time.time()
    m.record_run(
        mode="daily",
        result="ok",
        duration_s=1.5,
        units={"scanned": 3, "succeeded": 2, "skipped": 1, "failed": 0},
    )

    assert _value(m, "demo_worker_runs_total", '{mode="daily",result="ok"}') == 1
    assert _value(m, "demo_worker_run_duration_seconds", '{mode="daily"}') == 1.5
    assert (
        _value(m, "demo_worker_units_total", '{mode="daily",outcome="scanned"}') == 3
    )
    assert (
        _value(m, "demo_worker_units_total", '{mode="daily",outcome="succeeded"}') == 2
    )
    # 计数为 0 的单元不建序列，避免无意义的标签组合
    assert _value(m, "demo_worker_units_total", '{mode="daily",outcome="failed"}') == -1
    heartbeat = _value(m, "demo_worker_last_success_timestamp_seconds", '{mode="daily"}')
    assert before <= heartbeat <= time.time()


def test_non_ok_results_do_not_advance_heartbeat() -> None:
    m = _fresh()
    m.mark_process_start(("daily",))
    start_heartbeat = _value(
        m, "demo_worker_last_success_timestamp_seconds", '{mode="daily"}'
    )
    assert start_heartbeat > 0

    for result in ("failed", "disabled", "not_configured", "unsupported"):
        m.record_run(mode="daily", result=result)  # type: ignore[arg-type]

    assert (
        _value(m, "demo_worker_last_success_timestamp_seconds", '{mode="daily"}')
        == start_heartbeat
    )
    for result in ("failed", "disabled", "not_configured", "unsupported"):
        assert (
            _value(m, "demo_worker_runs_total", f'{{mode="daily",result="{result}"}}')
            == 1
        )


def test_heartbeat_is_per_mode() -> None:
    m = _fresh()
    m.mark_process_start(("daily", "sweep"))
    m.record_run(mode="daily", result="ok")
    daily = _value(m, "demo_worker_last_success_timestamp_seconds", '{mode="daily"}')
    sweep = _value(m, "demo_worker_last_success_timestamp_seconds", '{mode="sweep"}')
    assert daily >= sweep


def test_enabled_gauge_reflects_config() -> None:
    m = _fresh()
    m.set_enabled(False)
    assert _value(m, "demo_worker_enabled") == 0
    m.set_enabled(True)
    assert _value(m, "demo_worker_enabled") == 1


def test_unknown_result_is_rejected() -> None:
    m = _fresh()
    with pytest.raises(ValueError, match="unknown run result"):
        m.record_run(mode="daily", result="whatever")  # type: ignore[arg-type]


def test_start_metrics_server_disabled_and_enabled() -> None:
    m = _fresh()
    m.record_run(mode="daily", result="ok")

    assert start_metrics_server(0, m.registry) is None
    assert start_metrics_server(-1, m.registry) is None

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    server = start_metrics_server(port, m.registry, addr="127.0.0.1")
    assert server is not None
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=5
        ) as resp:
            body = resp.read().decode()
    finally:
        server.shutdown()

    assert 'demo_worker_runs_total{mode="daily",result="ok"} 1.0' in body
    assert "python_gc_objects_collected_total" not in body, (
        "worker 用独立 registry，不该带上进程默认指标"
    )

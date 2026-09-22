"""记忆治理 worker 的指标：把一次 Dream pass 运行的结果映射到 Prometheus。

指标清单（前缀 ``memory_governance``，见 ``app/core/worker_metrics.py``）：

- ``memory_governance_enabled`` / ``memory_governance_sweep_enabled``：配置开关
- ``memory_governance_runs_total{mode,result}``：日跑 / 周扫的结局
- ``memory_governance_last_success_timestamp_seconds{mode}``：心跳（staleness 告警）
- ``memory_governance_run_duration_seconds{mode}``：最近一次运行耗时
- ``memory_governance_units_total{mode,outcome}``：``scanned`` / ``succeeded`` /
  ``skipped`` / ``failed`` 的用户数
"""

from __future__ import annotations

from prometheus_client import Gauge

from app.core.worker_metrics import (
    RunResult,
    WorkerMetrics,
    start_metrics_server,
)
from app.services.memory_governance.service import DreamRunReport, RunMode

PREFIX = "memory_governance"
METRICS = WorkerMetrics(PREFIX)

MODES: tuple[RunMode, ...] = ("daily", "sweep")

SWEEP_ENABLED = Gauge(
    "memory_governance_sweep_enabled",
    "1 if the weekly sweep is enabled by configuration, 0 otherwise",
    registry=METRICS.registry,
)

# DreamRunReport.skip_reason -> runs_total 的 result 标签
_RESULT_BY_SKIP_REASON: dict[str, RunResult] = {
    "disabled": "disabled",
    "not_configured": "not_configured",
    "platform": "unsupported",
}


def set_flags(*, enabled: bool, sweep_enabled: bool) -> None:
    """刷新配置开关类 gauge（配置可能经 Nacos 热更新）。"""
    METRICS.set_enabled(enabled)
    SWEEP_ENABLED.set(1 if sweep_enabled else 0)


def mark_process_start() -> None:
    """两个 mode 的心跳都先写成进程启动时间，给新部署一个调度周期内的宽限期。"""
    METRICS.mark_process_start(MODES)


def start_server(port: int) -> bool:
    """按配置端口启动指标监听；``0`` 表示关闭。返回是否真的启动。"""
    return start_metrics_server(port, METRICS.registry) is not None


def record_report(report: DreamRunReport, *, duration_s: float) -> None:
    """汇报一次真实运行的结果。"""
    result: RunResult = "ok"
    if report.skip_reason is not None:
        # 未知的跳过原因一律当失败：宁可多告警，也不能把异常状态记成健康。
        result = _RESULT_BY_SKIP_REASON.get(report.skip_reason, "failed")
    METRICS.record_run(
        mode=report.mode,
        result=result,
        duration_s=duration_s,
        units={
            "scanned": report.scanned_users,
            "succeeded": report.succeeded,
            "skipped": report.skipped,
            "failed": report.failed,
        },
    )


def record_result(mode: RunMode, result: RunResult, *, duration_s: float = 0.0) -> None:
    """记录没有 report 的结局：调度层面就跳过了（disabled）或整轮异常（failed）。"""
    METRICS.record_run(mode=mode, result=result, duration_s=duration_s)


def record_failure(mode: RunMode, *, duration_s: float) -> None:
    """整轮抛异常（DB / Mem0 不可用等）。不推进心跳。"""
    METRICS.record_run(mode=mode, result="failed", duration_s=duration_s)

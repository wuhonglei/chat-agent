"""评估 worker 的指标：把一次批量评估的结果映射到 Prometheus。

指标清单（前缀 ``evaluator``，见 ``app/core/worker_metrics.py``）：

- ``evaluator_enabled``：配置开关
- ``evaluator_runs_total{mode,result}``：定时评估的结局（``mode`` 固定 ``scheduled``）
- ``evaluator_last_success_timestamp_seconds{mode}``：心跳（staleness 告警）
- ``evaluator_run_duration_seconds{mode}``：最近一次运行耗时
- ``evaluator_units_total{mode,outcome}``：``traces`` / ``sampled`` / ``judge_success``
  / ``judge_failed`` / ``low_score``
"""

from __future__ import annotations

from app.core.worker_metrics import RunResult, WorkerMetrics, start_metrics_server
from app.models.eval_run_log_db import EvalRunLog

PREFIX = "evaluator"
METRICS = WorkerMetrics(PREFIX)

# 定时评估只有一种运行类型（手动触发走 backend API，不经过本 worker），
# 保留 mode 标签是为了和治理 worker 的指标形状一致。
MODE = "scheduled"


def set_flags(*, enabled: bool) -> None:
    """刷新配置开关类 gauge（配置可能经 Nacos 热更新）。"""
    METRICS.set_enabled(enabled)


def mark_process_start() -> None:
    """心跳先写成进程启动时间，给新部署一个调度周期内的宽限期。"""
    METRICS.mark_process_start((MODE,))


def start_server(port: int) -> bool:
    """按配置端口启动指标监听；``0`` 表示关闭。返回是否真的启动。"""
    return start_metrics_server(port, METRICS.registry) is not None


def record_run_log(run_log: EvalRunLog, *, duration_s: float) -> None:
    """汇报一次批量评估的结果。``status`` 只有 ``success`` 算成功。"""
    result: RunResult = "ok" if run_log.status == "success" else "failed"
    METRICS.record_run(
        mode=MODE,
        result=result,
        duration_s=duration_s,
        units={
            "traces": run_log.total_traces,
            "sampled": run_log.sampled_count,
            "judge_success": run_log.judge_success,
            "judge_failed": run_log.judge_failed,
            "low_score": run_log.low_score_count,
        },
    )


def record_result(result: RunResult, *, duration_s: float = 0.0) -> None:
    """记录没有 run_log 的结局：调度层面就跳过了（disabled）。"""
    METRICS.record_run(mode=MODE, result=result, duration_s=duration_s)


def record_failure(*, duration_s: float) -> None:
    """整轮抛异常。不推进心跳。"""
    METRICS.record_run(mode=MODE, result="failed", duration_s=duration_s)

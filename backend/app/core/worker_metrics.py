"""常驻 worker（``eval_worker`` / ``memory_worker``）的 Prometheus 指标骨架。

backend 用 ``prometheus_fastapi_instrumentator`` 暴露 HTTP 指标；这两个 worker 没有
常驻 HTTP 端口，只有 APScheduler，所以这里用独立的 ``CollectorRegistry`` +
``start_http_server`` 另起一个监听，暴露「调度级」指标：

- ``{prefix}_enabled``：worker 是否启用（用于抑制「主动关闭」时的告警）
- ``{prefix}_runs_total{mode,result}``：每次调度运行的结局
  （``ok`` / ``failed`` / ``disabled`` / ``not_configured`` / ``unsupported``）
- ``{prefix}_last_success_timestamp_seconds{mode}``：心跳——最近一次成功运行的 Unix
  时间戳。staleness 告警基于它，而不是「日志里没有成功行」这种推断
- ``{prefix}_run_duration_seconds{mode}``：最近一次运行的耗时
- ``{prefix}_units_total{mode,outcome}``：运行处理的单元数（治理=用户，评估=样本/裁判）

约定：

- 只有 ``result="ok"`` 推进心跳；「配置缺失 / 后端不支持 / 主动关闭」只计数，不
  伪装成健康。
- 进程启动时用 :meth:`WorkerMetrics.mark_process_start` 把心跳初始化成启动时间，
  给新部署一个调度周期内的宽限期；「跑了但一直失败」由 ``result="failed"`` 覆盖，
  「反复重启」由容器级指标（cadvisor）覆盖。
- 不用 multiprocess 模式：worker 是单进程，若沿用 backend 的
  ``PROMETHEUS_MULTIPROC_DIR`` 反而会把指标混进 backend 的聚合目录。
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Literal
from wsgiref.simple_server import WSGIServer

from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server

RunResult = Literal["ok", "failed", "disabled", "not_configured", "unsupported"]
"""一次调度运行的结局。``ok`` 之外的取值都不推进心跳。"""

METRIC_RESULTS: tuple[RunResult, ...] = (
    "ok",
    "failed",
    "disabled",
    "not_configured",
    "unsupported",
)


class WorkerMetrics:
    """一个 worker 的全部调度级指标。

    ``prefix`` 同时是指标名前缀（``memory_governance`` / ``evaluator``）；自带独立
    registry，避免和 backend 的默认 registry 混在一起。
    """

    def __init__(
        self, prefix: str, *, registry: CollectorRegistry | None = None
    ) -> None:
        self.prefix = prefix
        self.registry = registry if registry is not None else CollectorRegistry()
        self.enabled = Gauge(
            f"{prefix}_enabled",
            "1 if the worker is enabled by configuration, 0 otherwise",
            registry=self.registry,
        )
        self.runs_total = Counter(
            f"{prefix}_runs_total",
            "Scheduled runs by outcome",
            ["mode", "result"],
            registry=self.registry,
        )
        self.last_success_timestamp_seconds = Gauge(
            f"{prefix}_last_success_timestamp_seconds",
            "Unix timestamp of the last successful run (heartbeat)",
            ["mode"],
            registry=self.registry,
        )
        self.run_duration_seconds = Gauge(
            f"{prefix}_run_duration_seconds",
            "Duration of the last run in seconds",
            ["mode"],
            registry=self.registry,
        )
        self.units_total = Counter(
            f"{prefix}_units_total",
            "Units handled by runs (users for governance, samples for eval)",
            ["mode", "outcome"],
            registry=self.registry,
        )

    def set_enabled(self, value: bool) -> None:
        """记录 worker 是否启用。配置关闭时用 ``1``/``0`` 抑制 staleness 告警。"""
        self.enabled.set(1 if value else 0)

    def mark_process_start(self, modes: Sequence[str]) -> None:
        """把各 ``mode`` 的心跳初始化为进程启动时间。

        给新部署一个「宽限期」：刚上线、还没到调度点时不应该告警。真正的
        「跑了但一直失败」由 ``runs_total{result="failed"}`` 告警覆盖。
        """
        now = time.time()
        for mode in modes:
            self.last_success_timestamp_seconds.labels(mode=mode).set(now)

    def record_run(
        self,
        *,
        mode: str,
        result: RunResult,
        duration_s: float | None = None,
        units: Mapping[str, int] | None = None,
    ) -> None:
        """记录一次运行：计数 + 耗时 + 处理单元数；``result="ok"`` 时推进心跳。"""
        if result not in METRIC_RESULTS:
            raise ValueError(f"unknown run result: {result!r}")
        self.runs_total.labels(mode=mode, result=result).inc()
        if duration_s is not None:
            self.run_duration_seconds.labels(mode=mode).set(duration_s)
        for outcome, count in (units or {}).items():
            if count:
                self.units_total.labels(mode=mode, outcome=outcome).inc(count)
        if result == "ok":
            self.last_success_timestamp_seconds.labels(mode=mode).set(time.time())


def start_metrics_server(
    port: int, registry: CollectorRegistry, *, addr: str = "0.0.0.0"
) -> WSGIServer | None:
    """启动指标 HTTP 服务；``port <= 0`` 表示关闭，返回 ``None``。

    返回 server 便于测试或调用方关闭；生产上跑在 daemon 线程里，进程退出即结束。
    """
    if port <= 0:
        return None
    server, _thread = start_http_server(port, addr=addr, registry=registry)
    return server

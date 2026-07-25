"""自定义进程级指标，兼容 gunicorn 多 worker + prometheus multiprocess 模式。

默认的 process_resident_memory_bytes / process_cpu_seconds_total
在 multiprocess 模式下不会被 MultiProcessCollector 正确聚合。
这里用 psutil 采集并写入带 pid label 的 Gauge，由 multiprocess 自动聚合。
"""

import os
import threading

import psutil
from prometheus_client import Gauge

# 带 pid label 的 Gauge，multiprocess 模式下会自动按 pid 聚合
PROCESS_RESIDENT_MEMORY = Gauge(
    "process_resident_memory_bytes_custom",
    "Resident memory size in bytes (custom, multiprocess-safe)",
    ["pid"],
)
PROCESS_CPU_SECONDS = Gauge(
    "process_cpu_seconds_total_custom",
    "Total user and system CPU time in seconds (custom, multiprocess-safe)",
    ["pid"],
)

_pid = str(os.getpid())
_process = psutil.Process()
_prev_cpu = _process.cpu_times()
_prev_cpu_total = _prev_cpu.user + _prev_cpu.system


def _update_metrics() -> None:
    """采集当前 worker 的内存和 CPU 并更新 Gauge。"""
    global _prev_cpu_total
    try:
        mem = _process.memory_info().rss
        PROCESS_RESIDENT_MEMORY.labels(pid=_pid).set(mem)

        cpu_times = _process.cpu_times()
        cpu_total = cpu_times.user + cpu_times.system
        PROCESS_CPU_SECONDS.labels(pid=_pid).set(cpu_total)
        _prev_cpu_total = cpu_total
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def start_process_metrics_collector(interval: float = 5.0) -> None:
    """启动后台线程，每 interval 秒采集一次进程指标。"""

    def _loop() -> None:
        while True:
            _update_metrics()
            threading.Event().wait(interval)

    t = threading.Thread(target=_loop, daemon=True, name="prom-process-metrics")
    t.start()

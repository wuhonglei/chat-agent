"""记忆治理 Worker 入口：APScheduler 定时按用户触发 Mem0 Dream pass。

两个 job：
- 日跑（``schedule_cron``，默认 04:00）：治理近 ``activity_within_days`` 天有聊天记录的用户
- 周扫（``sweep_cron``，默认周日 04:00）：从 Mem0 全量记忆列表发现沉睡用户，补治理存量碎片

与 ``eval_worker`` 同镜像、不同 command：``uv run python -m memory_worker.main``。
"""

from __future__ import annotations

import asyncio
import signal
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.observability import init_langfuse, shutdown_langfuse
from app.services.memory_governance.service import MemoryGovernanceService, RunMode
from app.utils.cron import parse_cron_5field
from app.utils.logger import logger
from memory_worker import metrics
from memory_worker.config import get_memory_governance_config

TIMEZONE = "Asia/Shanghai"


async def run_scheduled_governance(mode: RunMode = "daily") -> None:
    """定时记忆治理任务。

    异常只记录不上抛：启动即跑或调度触发时若 DB / Mem0 不可用，
    不应把 Worker 进程打挂（容器 restart 策略会变成重启风暴）。
    """
    logger.info("=== Scheduled memory governance started ===", mode=mode)
    started = time.perf_counter()
    try:
        report = await MemoryGovernanceService().run(mode=mode)
    except Exception as e:
        logger.error(
            "Scheduled memory governance failed", mode=mode, error=e, exc_info=True
        )
        metrics.record_failure(mode, duration_s=time.perf_counter() - started)
        return
    duration_s = time.perf_counter() - started
    metrics.record_report(report, duration_s=duration_s)
    logger.info("=== Scheduled memory governance finished ===", **report.to_dict())


async def main() -> None:
    """Worker 主循环。"""
    cfg = get_memory_governance_config()
    if not cfg.enabled:
        logger.warning(
            "Memory governance worker is disabled "
            "(memory_governance_worker.enabled=false); "
            "scheduler will still start but jobs are skipped unless enabled"
        )
    metrics.set_flags(enabled=cfg.enabled, sweep_enabled=cfg.sweep_enabled)
    metrics.mark_process_start()
    if metrics.start_server(cfg.metrics_port):
        logger.info(
            "Memory governance metrics endpoint listening", port=cfg.metrics_port
        )

    init_langfuse()

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    async def _job(mode: RunMode) -> None:
        current = get_memory_governance_config()
        metrics.set_flags(enabled=current.enabled, sweep_enabled=current.sweep_enabled)
        if not current.enabled:
            logger.info(
                "Memory governance worker disabled, skip scheduled run", mode=mode
            )
            metrics.record_result(mode, "disabled")
            return
        if mode == "sweep" and not current.sweep_enabled:
            logger.info("Memory governance sweep disabled, skip scheduled run")
            metrics.record_result(mode, "disabled")
            return
        await run_scheduled_governance(mode)

    scheduler.add_job(
        _job,
        kwargs={"mode": "daily"},
        trigger=CronTrigger(**parse_cron_5field(cfg.schedule_cron), timezone=TIMEZONE),
        id="memory_governance_daily",
        name="记忆治理 Dream pass（日跑）",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _job,
        kwargs={"mode": "sweep"},
        trigger=CronTrigger(**parse_cron_5field(cfg.sweep_cron), timezone=TIMEZONE),
        id="memory_governance_sweep",
        name="记忆治理 Dream pass（周扫）",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Memory governance worker started",
        schedule_cron=cfg.schedule_cron,
        sweep_cron=cfg.sweep_cron,
        sweep_enabled=cfg.sweep_enabled,
        enabled=cfg.enabled,
    )

    if cfg.enabled and cfg.run_on_startup:
        logger.info("memory_governance_worker.run_on_startup=true，启动即执行一次日跑")
        await run_scheduled_governance("daily")

    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    shutdown_langfuse()
    logger.info("Memory governance worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

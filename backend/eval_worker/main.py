"""评估 Worker 入口：APScheduler 定时触发批量评估。"""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.observability import init_langfuse
from app.services.eval.batch_eval_service import BatchEvalService
from app.services.eval.judge_llm import judge_llm_caller
from app.utils.logger import logger
from eval_worker.config import get_eval_worker_config


async def run_scheduled_eval() -> None:
    """定时评估任务。"""
    logger.info("=== Scheduled batch eval started ===")
    service = BatchEvalService(llm_caller=judge_llm_caller)
    run_log = await service.run(run_type="scheduled")
    logger.info(
        "=== Scheduled batch eval finished ===",
        run_id=run_log.id,
        status=run_log.status,
    )


def _parse_cron(cron: str) -> dict[str, Any]:
    """解析标准 5 段 cron: minute hour day month day_of_week。"""
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron}")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


async def main() -> None:
    """Worker 主循环。"""
    cfg = get_eval_worker_config()
    if not cfg.enabled:
        logger.warning(
            "Eval worker is disabled (eval_worker.enabled=false); "
            "scheduler will still start but jobs are skipped unless enabled"
        )

    init_langfuse()

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    cron_kwargs = _parse_cron(cfg.schedule_cron)

    async def _job() -> None:
        if not get_eval_worker_config().enabled:
            logger.info("Eval worker disabled, skip scheduled run")
            return
        await run_scheduled_eval()

    scheduler.add_job(
        _job,
        trigger=CronTrigger(**cron_kwargs, timezone="Asia/Shanghai"),
        id="batch_eval",
        name="定时批量评估",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Eval worker started",
        schedule_cron=cfg.schedule_cron,
        enabled=cfg.enabled,
    )

    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    logger.info("Eval worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

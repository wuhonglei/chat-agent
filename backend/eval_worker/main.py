"""评估 Worker 入口：APScheduler 定时触发批量评估。"""

from __future__ import annotations

import asyncio
import signal
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.observability import init_langfuse, shutdown_langfuse
from app.services.eval.batch_eval_service import BatchEvalService
from app.services.eval.judge_llm import judge_llm_caller
from app.utils.cron import parse_cron_5field
from app.utils.logger import logger
from eval_worker import metrics
from eval_worker.config import get_eval_worker_config


async def run_scheduled_eval() -> None:
    """定时评估任务。"""
    logger.info("=== Scheduled batch eval started ===")
    started = time.perf_counter()
    try:
        service = BatchEvalService(llm_caller=judge_llm_caller)
        run_log = await service.run(run_type="scheduled")
    except Exception as e:
        logger.error("=== Scheduled batch eval raised ===", error=e, exc_info=True)
        metrics.record_failure(duration_s=time.perf_counter() - started)
        return
    duration_s = time.perf_counter() - started
    metrics.record_run_log(run_log, duration_s=duration_s)
    logger.info(
        "=== Scheduled batch eval finished ===",
        run_id=run_log.id,
        status=run_log.status,
    )


async def main() -> None:
    """Worker 主循环。"""
    cfg = get_eval_worker_config()
    if not cfg.enabled:
        logger.warning(
            "Eval worker is disabled (eval_worker.enabled=false); "
            "scheduler will still start but jobs are skipped unless enabled"
        )
    metrics.set_flags(enabled=cfg.enabled)
    metrics.mark_process_start()
    if metrics.start_server(cfg.metrics_port):
        logger.info("Evaluator metrics endpoint listening", port=cfg.metrics_port)

    init_langfuse()

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    cron_kwargs = parse_cron_5field(cfg.schedule_cron)

    async def _job() -> None:
        current = get_eval_worker_config()
        metrics.set_flags(enabled=current.enabled)
        if not current.enabled:
            logger.info("Eval worker disabled, skip scheduled run")
            metrics.record_result("disabled")
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
    shutdown_langfuse()
    logger.info("Eval worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

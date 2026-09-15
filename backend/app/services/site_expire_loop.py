"""Periodic unpublish of expired static sites (nginx only honors ``current``)."""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.services.site_publish_service import SitePublishService
from app.utils.logger import logger


def expire_due_sites_once() -> int:
    with SitePublishService() as service:
        return service.expire_due_sites()


async def run_site_expire_loop(stop: asyncio.Event) -> None:
    interval = settings.sites.expire_interval_seconds
    if interval <= 0:
        logger.info("Site expire loop disabled")
        return
    logger.info("Site expire loop started", interval_seconds=interval)
    while not stop.is_set():
        try:
            expired = await asyncio.to_thread(expire_due_sites_once)
            if expired:
                logger.info("Site expire loop unpublished sites", count=expired)
        except Exception as exc:
            logger.error("Site expire loop failed", error=exc, exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue
    logger.info("Site expire loop stopped")

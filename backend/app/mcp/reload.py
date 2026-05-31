"""Schedule MCPClientManager reload when ``settings.mcp`` changes."""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import Future
from typing import TYPE_CHECKING

from app.schemas.config import MCPConfig
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.mcp.client import MCPClientManager

_register_lock = threading.Lock()
_event_loop: asyncio.AbstractEventLoop | None = None
_manager: MCPClientManager | None = None
_last_fingerprint: str | None = None


def mcp_config_fingerprint(mcp: MCPConfig) -> str:
    """Stable fingerprint for MCP server wiring."""
    payload = {
        "mcp_servers": {
            name: entry.model_dump(mode="json")
            for name, entry in sorted(mcp.mcp_servers.items())
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def register_mcp_reload_target(
    loop: asyncio.AbstractEventLoop,
    manager: MCPClientManager,
) -> None:
    """Called from FastAPI lifespan after MCP manager is initialized."""
    global _event_loop, _manager, _last_fingerprint
    from app.core.config import settings

    with _register_lock:
        _event_loop = loop
        _manager = manager
        _last_fingerprint = mcp_config_fingerprint(settings.mcp)
    logger.info(
        "MCP reload target registered",
        fingerprint=_last_fingerprint[:16] + "…"
        if _last_fingerprint and len(_last_fingerprint) > 16
        else _last_fingerprint,
    )


def on_settings_reloaded() -> bool:
    """Compare MCP fingerprint after ``reload_settings()``; schedule reload if changed."""
    from app.core.config import settings

    global _last_fingerprint
    new_fp = mcp_config_fingerprint(settings.mcp)
    with _register_lock:
        old_fp = _last_fingerprint
        if old_fp == new_fp:
            return False
        _last_fingerprint = new_fp
        loop = _event_loop
        manager = _manager

    logger.info(
        "MCP 配置已变更，准备热更新 MCP Manager",
        old_fingerprint=(old_fp[:16] + "…") if old_fp and len(old_fp) > 16 else old_fp,
        new_fingerprint=new_fp[:16] + "…" if len(new_fp) > 16 else new_fp,
    )
    schedule_mcp_reload(loop=loop, manager=manager)
    return True


def schedule_mcp_reload(
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    manager: MCPClientManager | None = None,
) -> None:
    """Submit ``reload_async`` to the app event loop (safe from Nacos listener thread)."""
    target_loop = loop if loop is not None else _event_loop
    target_manager = manager if manager is not None else _manager
    if target_loop is None or target_manager is None:
        logger.debug(
            "MCP reload skipped: event loop or manager not registered yet",
        )
        return

    def _done_callback(fut: Future[None]) -> None:
        try:
            fut.result()
        except Exception as exc:
            logger.error(
                "MCP Manager 热更新失败",
                error=exc,
                exc_info=True,
            )

    future = asyncio.run_coroutine_threadsafe(
        target_manager.reload_async(),
        target_loop,
    )
    future.add_done_callback(_done_callback)

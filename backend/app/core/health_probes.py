"""Dependency probes for live / ready / deep health endpoints."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal, TypedDict, cast

from openai import AsyncOpenAI

from app.core.db import get_pool_stats, probe_db_sync
from app.core.health_metrics import record_db_pool_stats, record_dependency
from app.core.local_cache import l1_get, l1_set
from app.core.redis import ping_redis
from app.utils.logger import logger

ProbeStatus = Literal["ok", "unavailable"]

_PROBE_TIMEOUT_SECONDS = 3.0
_LLM_CACHE_KEY = "llm_probe"


class ProbeResult(TypedDict):
    status: ProbeStatus
    latency_ms: float
    error: str | None


def _status(ok: bool) -> ProbeStatus:
    return "ok" if ok else "unavailable"


def _cached_probe(namespace: str, key: str) -> ProbeResult | None:
    cached = l1_get(namespace, key)
    if isinstance(cached, dict) and "status" in cached and "latency_ms" in cached:
        return cast(ProbeResult, cached)
    return None


async def probe_postgres(*, use_cache: bool = True) -> ProbeResult:
    """Probe Postgres with SELECT 1."""
    if use_cache:
        cached = _cached_probe("health", "postgres")
        if cached is not None:
            return cached

    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(probe_db_sync),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        latency_ms = (time.perf_counter() - started) * 1000.0
        result = {
            "ok": False,
            "latency_ms": round(latency_ms, 2),
            "error": f"timeout after {_PROBE_TIMEOUT_SECONDS}s",
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        result = {
            "ok": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(exc),
        }

    latency_ms = float(result.get("latency_ms") or 0.0)
    payload: ProbeResult = {
        "status": _status(bool(result.get("ok"))),
        "latency_ms": latency_ms,
        "error": cast(str | None, result.get("error")),
    }
    record_dependency(
        "postgres",
        up=payload["status"] == "ok",
        latency_seconds=latency_ms / 1000.0,
    )
    if use_cache:
        l1_set("health", "postgres", payload)
    return payload


async def probe_redis_dep(*, use_cache: bool = True) -> ProbeResult:
    """Probe Redis with PING."""
    if use_cache:
        cached = _cached_probe("health", "redis")
        if cached is not None:
            return cached

    started = time.perf_counter()
    try:
        ok = await asyncio.wait_for(ping_redis(), timeout=_PROBE_TIMEOUT_SECONDS)
        error: str | None = None if ok else "ping failed"
    except TimeoutError:
        ok = False
        error = f"timeout after {_PROBE_TIMEOUT_SECONDS}s"
    except Exception as exc:
        ok = False
        error = str(exc)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    payload: ProbeResult = {
        "status": _status(ok),
        "latency_ms": latency_ms,
        "error": error,
    }
    record_dependency(
        "redis",
        up=payload["status"] == "ok",
        latency_seconds=latency_ms / 1000.0,
    )
    if use_cache:
        l1_set("health", "redis", payload)
    return payload


async def probe_llm(*, use_cache: bool = True) -> ProbeResult:
    """Light LLM reachability check via models.list() (text_generation scenario)."""
    if use_cache:
        cached = _cached_probe("health_llm", _LLM_CACHE_KEY)
        if cached is not None:
            return cached

    started = time.perf_counter()
    client: AsyncOpenAI | None = None
    try:
        from app.services.base_service.model_resolver import resolve_scenario

        llm_config = resolve_scenario("text_generation")
        client = AsyncOpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
            timeout=_PROBE_TIMEOUT_SECONDS,
            max_retries=0,
        )
        await asyncio.wait_for(client.models.list(), timeout=_PROBE_TIMEOUT_SECONDS)
        ok = True
        error = None
    except Exception as exc:
        ok = False
        error = str(exc)
        logger.warning("LLM health probe failed", error=exc)
    finally:
        if client is not None:
            await client.close()

    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    payload: ProbeResult = {
        "status": _status(ok),
        "latency_ms": latency_ms,
        "error": error,
    }
    record_dependency(
        "llm",
        up=payload["status"] == "ok",
        latency_seconds=latency_ms / 1000.0,
    )
    if use_cache:
        l1_set("health_llm", _LLM_CACHE_KEY, payload)
    return payload


def collect_pool_stats() -> dict[str, int]:
    """Read pool stats and publish Prometheus gauges."""
    stats = get_pool_stats()
    record_db_pool_stats(
        size=stats["size"],
        checkedout=stats["checkedout"],
        overflow=stats["overflow"],
    )
    return stats


async def run_ready_probes() -> dict[str, Any]:
    """Postgres + Redis for readiness."""
    postgres, redis = await asyncio.gather(
        probe_postgres(),
        probe_redis_dep(),
    )
    pool = collect_pool_stats()
    hard_ok = postgres["status"] == "ok" and redis["status"] == "ok"
    return {
        "status": "healthy" if hard_ok else "unhealthy",
        "postgres": postgres,
        "redis": redis,
        "db_pool": pool,
        "ready": hard_ok,
    }


async def run_deep_probes() -> dict[str, Any]:
    """Postgres + Redis + pool + LLM for deep diagnostics."""
    postgres, redis, llm = await asyncio.gather(
        probe_postgres(),
        probe_redis_dep(),
        probe_llm(),
    )
    pool = collect_pool_stats()
    hard_ok = postgres["status"] == "ok" and redis["status"] == "ok"
    if not hard_ok:
        overall = "unhealthy"
    elif llm["status"] != "ok":
        overall = "degraded"
    else:
        overall = "healthy"
    return {
        "status": overall,
        "postgres": postgres,
        "redis": redis,
        "llm": llm,
        "db_pool": pool,
        "ready": hard_ok,
    }

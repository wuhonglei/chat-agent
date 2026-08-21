"""Tests for live / ready / deep health endpoints and probe caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import JSONResponse

from app.api import health as health_api
from app.core import local_cache
from app.core.health_probes import (
    probe_llm,
    probe_postgres,
    probe_redis_dep,
    run_deep_probes,
    run_ready_probes,
)
from app.middleware.logging import should_skip_logging


@pytest.fixture(autouse=True)
def _clear_health_cache() -> None:
    local_cache.l1_delete("health")
    local_cache.l1_delete("health_llm")
    yield
    local_cache.l1_delete("health")
    local_cache.l1_delete("health_llm")


@pytest.mark.asyncio
async def test_live_always_200_even_if_deps_down() -> None:
    response = await health_api.health_live()
    assert response.code == 0
    assert response.data is not None
    assert response.data["status"] == "alive"


@pytest.mark.asyncio
async def test_ready_503_when_postgres_down() -> None:
    with (
        patch(
            "app.core.health_probes.probe_postgres",
            new=AsyncMock(
                return_value={
                    "status": "unavailable",
                    "latency_ms": 1.0,
                    "error": "down",
                }
            ),
        ),
        patch(
            "app.core.health_probes.probe_redis_dep",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.collect_pool_stats",
            return_value={"size": 5, "checkedout": 0, "overflow": 0, "checkedin": 5},
        ),
    ):
        response = await health_api.health_ready()

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    body = response.body
    assert b'"status":"unhealthy"' in body or b'"status": "unhealthy"' in body


@pytest.mark.asyncio
async def test_ready_200_when_hard_deps_ok() -> None:
    with (
        patch(
            "app.core.health_probes.probe_postgres",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.probe_redis_dep",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.collect_pool_stats",
            return_value={"size": 5, "checkedout": 1, "overflow": 0, "checkedin": 4},
        ),
    ):
        response = await health_api.health_ready()

    assert not isinstance(response, JSONResponse)
    assert response.code == 0
    assert response.data is not None
    assert response.data["status"] == "healthy"
    assert response.data["ready"] is True


@pytest.mark.asyncio
async def test_deep_degraded_when_llm_fails_but_hard_deps_ok() -> None:
    with (
        patch(
            "app.core.health_probes.probe_postgres",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.probe_redis_dep",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.probe_llm",
            new=AsyncMock(
                return_value={
                    "status": "unavailable",
                    "latency_ms": 2.0,
                    "error": "timeout",
                }
            ),
        ),
        patch(
            "app.core.health_probes.collect_pool_stats",
            return_value={"size": 5, "checkedout": 0, "overflow": 0, "checkedin": 5},
        ),
    ):
        response = await health_api.health_check()

    assert not isinstance(response, JSONResponse)
    assert response.code == 0
    assert response.data is not None
    assert response.data["status"] == "degraded"
    assert response.data["ready"] is True
    assert "db_pool" in response.data
    assert response.data["db_pool"]["size"] == 5


@pytest.mark.asyncio
async def test_deep_503_when_redis_down() -> None:
    with (
        patch(
            "app.core.health_probes.probe_postgres",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.probe_redis_dep",
            new=AsyncMock(
                return_value={
                    "status": "unavailable",
                    "latency_ms": 1.0,
                    "error": "down",
                }
            ),
        ),
        patch(
            "app.core.health_probes.probe_llm",
            new=AsyncMock(
                return_value={"status": "ok", "latency_ms": 1.0, "error": None}
            ),
        ),
        patch(
            "app.core.health_probes.collect_pool_stats",
            return_value={"size": 5, "checkedout": 0, "overflow": 0, "checkedin": 5},
        ),
    ):
        response = await health_api.health_check()

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_health_l1_cache_holds_multiple_keys() -> None:
    local_cache.l1_set("health", "postgres", {"status": "ok"})
    local_cache.l1_set("health", "redis", {"status": "ok"})
    local_cache.l1_set("health_llm", "llm_probe", {"status": "ok"})

    assert local_cache.l1_get("health", "postgres") == {"status": "ok"}
    assert local_cache.l1_get("health", "redis") == {"status": "ok"}
    assert local_cache.l1_get("health_llm", "llm_probe") == {"status": "ok"}


@pytest.mark.asyncio
async def test_probe_redis_uses_cache() -> None:
    with patch(
        "app.core.health_probes.ping_redis", new=AsyncMock(return_value=True)
    ) as ping:
        first = await probe_redis_dep()
        second = await probe_redis_dep()

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert ping.await_count == 1


@pytest.mark.asyncio
async def test_probe_postgres_records_failure() -> None:
    with patch(
        "app.core.health_probes.probe_db_sync",
        return_value={"ok": False, "latency_ms": 3.0, "error": "boom"},
    ):
        result = await probe_postgres(use_cache=False)

    assert result["status"] == "unavailable"
    assert result["error"] == "boom"


@pytest.mark.asyncio
async def test_probe_llm_failure_does_not_raise() -> None:
    with patch(
        "app.services.base_service.model_resolver.resolve_scenario",
        side_effect=RuntimeError("no model"),
    ):
        result = await probe_llm(use_cache=False)

    assert result["status"] == "unavailable"
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_run_ready_and_deep_aggregate() -> None:
    ok = {"status": "ok", "latency_ms": 1.0, "error": None}
    with (
        patch("app.core.health_probes.probe_postgres", new=AsyncMock(return_value=ok)),
        patch("app.core.health_probes.probe_redis_dep", new=AsyncMock(return_value=ok)),
        patch("app.core.health_probes.probe_llm", new=AsyncMock(return_value=ok)),
        patch(
            "app.core.health_probes.collect_pool_stats",
            return_value={"size": 5, "checkedout": 0, "overflow": 0, "checkedin": 5},
        ),
    ):
        ready = await run_ready_probes()
        deep = await run_deep_probes()

    assert ready["ready"] is True
    assert deep["status"] == "healthy"
    assert deep["llm"]["status"] == "ok"


def test_should_skip_logging_health_prefix() -> None:
    assert should_skip_logging("/api/health") is True
    assert should_skip_logging("/api/health/live") is True
    assert should_skip_logging("/api/health/ready") is True
    assert should_skip_logging("/api/chat") is False

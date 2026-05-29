"""Tests for MCP config fingerprint and reload scheduling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.mcp.reload import (
    mcp_config_fingerprint,
    on_settings_reloaded,
    register_mcp_reload_target,
)
from app.schemas.config import MCPConfig, MCPServerEntry


def test_mcp_config_fingerprint_stable_for_same_config() -> None:
    mcp = MCPConfig(
        servers={
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
            ),
        },
    )
    assert mcp_config_fingerprint(mcp) == mcp_config_fingerprint(mcp)


def test_mcp_config_fingerprint_changes_when_server_disabled() -> None:
    base = MCPConfig(
        servers={
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
                enabled=True,
            ),
        },
    )
    disabled = MCPConfig(
        servers={
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
                enabled=False,
            ),
        },
    )
    assert mcp_config_fingerprint(base) != mcp_config_fingerprint(disabled)


@pytest.mark.asyncio
async def test_on_settings_reloaded_schedules_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.mcp.reload as reload_mod

    manager = MagicMock()
    manager.reload_async = AsyncMock()
    loop = asyncio.get_running_loop()
    register_mcp_reload_target(loop, manager)

    mcp_a = MCPConfig(
        servers={
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
            ),
        },
    )
    mcp_b = MCPConfig(
        servers={
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
                enabled=False,
            ),
        },
    )

    settings_mock = MagicMock()
    settings_mock.mcp = mcp_a
    monkeypatch.setattr("app.core.config.settings", settings_mock)
    reload_mod._last_fingerprint = mcp_config_fingerprint(mcp_a)

    settings_mock.mcp = mcp_b
    assert on_settings_reloaded() is True
    await asyncio.sleep(0.05)
    manager.reload_async.assert_awaited_once()

    assert on_settings_reloaded() is False

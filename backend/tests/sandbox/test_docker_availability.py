"""Tests for Docker availability helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.sandbox.docker_availability import (
    is_docker_daemon_available,
    reset_docker_availability_cache,
)


def test_is_docker_daemon_available_when_ping_succeeds() -> None:
    reset_docker_availability_cache()
    mock_client = MagicMock()
    with patch("docker.from_env", return_value=mock_client):
        assert is_docker_daemon_available(force_refresh=True) is True
    mock_client.ping.assert_called_once()


def test_is_docker_daemon_available_when_ping_fails() -> None:
    reset_docker_availability_cache()
    with patch("docker.from_env", side_effect=ConnectionRefusedError(61, "refused")):
        assert is_docker_daemon_available(force_refresh=True) is False

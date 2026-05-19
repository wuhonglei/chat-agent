"""Docker daemon availability checks."""

from __future__ import annotations

_docker_available: bool | None = None


def is_docker_daemon_available(*, force_refresh: bool = False) -> bool:
    """Return True when the Docker daemon responds to ping."""
    global _docker_available

    if not force_refresh and _docker_available is not None:
        return _docker_available

    try:
        import docker

        client = docker.from_env()
        client.ping()
        _docker_available = True
    except Exception:
        _docker_available = False

    return _docker_available


def reset_docker_availability_cache() -> None:
    """Clear cached availability (for tests)."""
    global _docker_available
    _docker_available = None

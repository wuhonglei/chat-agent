"""Thread-safe process-local caches for small global responses."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from cachetools import TTLCache

from app.utils.logger import logger


@dataclass(frozen=True)
class _CacheConfig:
    maxsize: int
    ttl: float


_CACHE_CONFIGS = {
    "models": _CacheConfig(maxsize=1, ttl=300),
    "health": _CacheConfig(maxsize=1, ttl=5),
}
_caches: dict[str, TTLCache[str, Any]] = {}
_lock = RLock()


def _get_cache(namespace: str) -> TTLCache[str, Any]:
    config = _CACHE_CONFIGS.get(namespace)
    if config is None:
        raise ValueError(f"Unsupported L1 cache namespace: {namespace}")
    cache = _caches.get(namespace)
    if cache is None:
        cache = TTLCache[str, Any](maxsize=config.maxsize, ttl=config.ttl)
        _caches[namespace] = cache
    return cache


def l1_get(namespace: str, key: str) -> Any | None:
    """Return a cached value, or ``None`` on miss/expiry."""
    with _lock:
        value = _get_cache(namespace).get(key)
    logger.debug(
        "cache_hit" if value is not None else "cache_miss",
        cache_level="l1",
        cache_namespace=namespace,
    )
    return value


def l1_set(namespace: str, key: str, value: Any) -> None:
    """Store a value using the namespace's fixed size and TTL."""
    with _lock:
        _get_cache(namespace)[key] = value


def l1_delete(namespace: str, key: str | None = None) -> None:
    """Delete one key, or clear the complete namespace when key is ``None``."""
    with _lock:
        cache = _caches.get(namespace)
        if cache is None:
            return
        if key is None:
            cache.clear()
        else:
            cache.pop(key, None)
    logger.info(
        "cache_invalidate",
        cache_level="l1",
        cache_namespace=namespace,
        cache_key=key,
    )

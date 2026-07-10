"""Redis 异步连接池"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import quote

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings
from app.utils.logger import logger

_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


def _build_redis_url() -> str:
    cfg = settings.redis
    userinfo = ""
    if cfg.username or cfg.password:
        user = quote(cfg.username, safe="")
        password = quote(cfg.password, safe="")
        userinfo = f"{user}:{password}@"
    return f"redis://{userinfo}{cfg.host}:{cfg.port}/0"


def _redis_socket_timeout_seconds() -> float:
    """Read timeout must exceed SSE XREAD BLOCK duration (redis-py default is ~5s)."""
    block_seconds = settings.chat_stream.sse_stream_xread_block_ms / 1000.0
    return block_seconds + 5.0


async def init_redis() -> Redis:
    """创建连接池并在启动时探测连通性。"""
    global _redis_pool, _redis_client
    if _redis_client is not None:
        return _redis_client

    socket_timeout = _redis_socket_timeout_seconds()
    _redis_pool = ConnectionPool.from_url(
        _build_redis_url(),
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5.0,
        socket_timeout=socket_timeout,
    )
    _redis_client = Redis.from_pool(_redis_pool)
    await _redis_client.ping()
    logger.info(
        "Redis connected",
        host=settings.redis.host,
        port=settings.redis.port,
        username=settings.redis.username,
    )
    return _redis_client


async def close_redis() -> None:
    """关闭共享客户端与连接池。"""
    global _redis_pool, _redis_client
    if _redis_client is None:
        return
    await _redis_client.aclose()
    _redis_client = None
    _redis_pool = None
    logger.info("Redis disconnected")


def get_redis() -> Redis:
    """获取进程内共享 Redis 客户端。"""
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized; call init_redis() during startup"
        )
    return _redis_client


async def get_redis_dep() -> AsyncGenerator[Redis, None]:
    """FastAPI 依赖：返回共享 Redis 客户端。"""
    yield get_redis()


async def ping_redis() -> bool:
    """探测 Redis 是否可用。"""
    try:
        return await get_redis().ping() is True
    except Exception:
        return False

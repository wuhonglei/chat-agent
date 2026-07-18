"""client_turn_id 幂等存储（Redis），供多 worker 共享。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException

from app.core.config import settings
from app.core.redis import get_redis
from app.utils.logger import logger

PENDING_SENTINEL = "pending"


@dataclass(frozen=True)
class IdempotentTurn:
    user_message_id: str
    assistant_message_id: str


class TurnIdempotencyStore:
    """将一轮对话的消息 ID 对缓存到 Redis，避免重复 create_chat_messages。"""

    KEY_PREFIX = "chat:turn:"

    def __init__(
        self,
        *,
        ttl_seconds: int | None = None,
        pending_ttl_seconds: int | None = None,
        wait_timeout_seconds: float | None = None,
    ) -> None:
        cfg = settings.chat_stream
        self._ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else cfg.turn_idempotency_ttl_seconds
        )
        self._pending_ttl_seconds = (
            pending_ttl_seconds
            if pending_ttl_seconds is not None
            else cfg.turn_idempotency_pending_ttl_seconds
        )
        self._wait_timeout_seconds = (
            wait_timeout_seconds
            if wait_timeout_seconds is not None
            else cfg.turn_idempotency_wait_timeout_seconds
        )

    def _key(self, key: tuple[str, str, str]) -> str:
        user_id, conversation_id, client_turn_id = key
        return f"{self.KEY_PREFIX}{user_id}:{conversation_id}:{client_turn_id}"

    @staticmethod
    def _as_str(value: bytes | str) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return value

    def _parse_turn(self, raw: str) -> IdempotentTurn | None:
        if not raw or raw == PENDING_SENTINEL:
            return None
        try:
            data = json.loads(raw)
            return IdempotentTurn(
                user_message_id=str(data["user_message_id"]),
                assistant_message_id=str(data["assistant_message_id"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    async def get(self, key: tuple[str, str, str]) -> IdempotentTurn | None:
        raw = await get_redis().get(self._key(key))
        if raw is None:
            return None
        return self._parse_turn(self._as_str(raw))

    async def save(self, key: tuple[str, str, str], turn: IdempotentTurn) -> None:
        payload = json.dumps(
            {
                "user_message_id": turn.user_message_id,
                "assistant_message_id": turn.assistant_message_id,
            },
            ensure_ascii=False,
        )
        await get_redis().set(self._key(key), payload, ex=self._ttl_seconds)

    async def reserve_or_get(
        self, key: tuple[str, str, str]
    ) -> IdempotentTurn | Literal["reserved"]:
        """尝试占位或返回已有 turn。

        - SET NX pending 成功 → ``\"reserved\"``（当前 worker 负责建消息）
        - 已有 JSON → 返回 ``IdempotentTurn``
        - 为 pending → 短轮询等待 winner 写回；超时抛 503
        """
        redis = get_redis()
        redis_key = self._key(key)
        reserved = await redis.set(
            redis_key,
            PENDING_SENTINEL,
            nx=True,
            ex=self._pending_ttl_seconds,
        )
        if reserved:
            return "reserved"

        deadline = asyncio.get_running_loop().time() + self._wait_timeout_seconds
        while True:
            raw = await redis.get(redis_key)
            if raw is None:
                # pending 过期且 winner 未写回：再尝试占位
                reserved_again = await redis.set(
                    redis_key,
                    PENDING_SENTINEL,
                    nx=True,
                    ex=self._pending_ttl_seconds,
                )
                if reserved_again:
                    return "reserved"
                await asyncio.sleep(0.1)
                continue

            turn = self._parse_turn(self._as_str(raw))
            if turn is not None:
                return turn

            if asyncio.get_running_loop().time() >= deadline:
                logger.warning(
                    "Turn idempotency wait timed out",
                    redis_key=redis_key,
                    wait_timeout_seconds=self._wait_timeout_seconds,
                )
                raise HTTPException(
                    status_code=503,
                    detail="对话幂等处理繁忙，请稍后重试",
                )
            await asyncio.sleep(0.1)

    async def resolve_turn(
        self,
        key: tuple[str, str, str],
        *,
        create_fn: Callable[[], Awaitable[IdempotentTurn]],
    ) -> tuple[IdempotentTurn, bool]:
        """返回 ``(turn, is_idempotent_hit)``。

        ``is_idempotent_hit=True`` 表示复用已有消息，不应再启动新 producer。
        """
        result = await self.reserve_or_get(key)
        if result != "reserved":
            return result, True

        try:
            turn = await create_fn()
            await self.save(key, turn)
            return turn, False
        except Exception:
            # 释放 pending，避免其他请求长时间阻塞
            redis = get_redis()
            redis_key = self._key(key)
            current = await redis.get(redis_key)
            if current == PENDING_SENTINEL:
                await redis.delete(redis_key)
            raise

"""Mem0 记忆服务：封装 Mem0 REST API（写入、搜索、列表、删除）"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.observability import mark_observation_error, observation_span
from app.schemas.config import MemoryConfig
from app.schemas.user import MemoryListItem
from app.utils.logger import logger


class MemoryService:
    """Mem0 记忆服务，使用 httpx 调用 Mem0 REST API。"""

    def __init__(self, config: MemoryConfig) -> None:
        self.config = config
        self._timeout = 30.0

    def _base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def _mem0_enabled(self) -> bool:
        return bool(self.config.base_url.strip()) and bool(self.config.api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.config.api_key.strip(),
        }

    async def add_memories(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """写入记忆：POST /memories，传入 messages + user_id。

        异步 fire-and-forget 调用，不在 Langfuse 中单独建 trace，避免与 chat-turn
        共用 trace_id 时产生第二条 root observation。
        """
        if not self._mem0_enabled():
            return
        url = f"{self._base_url()}/memories"
        body: dict[str, Any] = {
            "messages": messages,
            "user_id": user_id,
        }
        if run_id is not None:
            body["run_id"] = run_id
        if metadata is not None:
            body["metadata"] = metadata
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body, headers=self._headers())
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 add_memories failed",
                user_id=user_id,
                error=e,
            )

    async def search(
        self,
        query: str,
        user_id: str,
        threshold: float | None = None,
        limit: int | None = None,
    ) -> list[MemoryListItem]:
        """搜索记忆：POST /search，返回记忆文本列表。"""
        if not self._mem0_enabled():
            return []
        url = f"{self._base_url()}/search"
        limit = limit if limit is not None else self.config.search_limit
        body: dict[str, Any] = {
            "query": query,
            "filters": {"user_id": user_id},
            "top_k": limit,
        }
        if threshold is not None:
            body["threshold"] = threshold
        with observation_span(
            "memory-search",
            input={"query": query, "top_k": limit},
        ) as span:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=body, headers=self._headers())
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPError as e:
                mark_observation_error(span, e)
                logger.warning(
                    "Mem0 search failed",
                    user_id=user_id,
                    error=e,
                )
                return []

            results = data.get("results") if isinstance(data, dict) else []
            if not isinstance(results, list):
                return []
            r: list[MemoryListItem] = [MemoryListItem(**item) for item in results]
            r.sort(
                key=lambda x: x.score if x.score is not None else float("-inf"),
                reverse=True,
            )
            r = r[:limit]
            if span is not None:
                span.update(
                    output={
                        "count": len(r),
                        "memory_ids": [item.id for item in r],
                    }
                )
            return r

    async def get_memories(self, user_id: str) -> list[MemoryListItem]:
        """获取用户记忆列表：GET /memories?user_id=。"""
        if not self._mem0_enabled():
            return []
        url = f"{self._base_url()}/memories"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url, params={"user_id": user_id}, headers=self._headers()
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 get_memories failed",
                user_id=user_id,
                error=e,
            )
            return []

        res: list[MemoryListItem] = []
        if isinstance(data, list):
            res = [MemoryListItem(**item) for item in data]
        if isinstance(data, dict) and "results" in data:
            r = data["results"]
            res = [MemoryListItem(**item) for item in r] if isinstance(r, list) else []
        res.sort(key=lambda x: x.created_at, reverse=True)
        return res

    async def delete_memory(self, memory_id: str) -> None:
        """删除单条记忆：DELETE /memories/{memory_id}。"""
        if not self._mem0_enabled():
            return
        url = f"{self._base_url()}/memories/{memory_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.delete(url, headers=self._headers())
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 delete_memory failed",
                memory_id=memory_id,
                error=e,
            )
            raise

    async def delete_all_memories(self, user_id: str) -> None:
        """按 user_id 删除全部记忆：DELETE /memories?user_id=。"""
        if not self._mem0_enabled():
            return
        url = f"{self._base_url()}/memories"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.delete(
                    url, params={"user_id": user_id}, headers=self._headers()
                )
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 delete_all_memories failed",
                user_id=user_id,
                error=e,
            )
            raise

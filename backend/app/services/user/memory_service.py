"""Mem0 记忆服务：封装 Mem0 REST API（写入、搜索、列表、按 id 查询、删除）"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.core.observability import mark_observation_error, observation_span
from app.schemas.config import MemoryConfig
from app.schemas.user import (
    MemoryGovernanceStatus,
    MemoryKindQuery,
    MemoryListItem,
    MemoryListResponse,
)
from app.utils.logger import logger


class MemoryService:
    """Mem0 记忆服务，使用 httpx 调用 Mem0 REST API。

    商业版 Platform（``api.mem0.ai`` 或 base_url 以 ``/v3`` 结尾）走 v3 分路径接口，
    且必须带尾斜杠（否则 Django 会 301，httpx 默认不跟随 POST 重定向）。
    自建 OSS 仍使用 ``/memories``、``/search``。
    """

    def __init__(self, config: MemoryConfig) -> None:
        self.config = config
        self._timeout = 30.0
        self._search_timeout = 5.0

    def _base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def _origin(self) -> str:
        parsed = urlparse(self.config.base_url.strip())
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return self._base_url()

    def _is_platform(self) -> bool:
        parsed = urlparse(self.config.base_url.strip())
        host = (parsed.netloc or "").split("@")[-1].split(":")[0].lower()
        path = (parsed.path or "").rstrip("/")
        return host == "api.mem0.ai" or path.endswith("/v3")

    def _mem0_enabled(self) -> bool:
        return bool(self.config.base_url.strip()) and bool(self.config.api_key.strip())

    def _headers(self) -> dict[str, str]:
        api_key = self.config.api_key.strip()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": api_key,
            "Authorization": f"Token {api_key}",
        }

    def _add_url(self) -> str:
        if self._is_platform():
            return f"{self._origin()}/v3/memories/add/"
        return f"{self._base_url()}/memories"

    def _search_url(self) -> str:
        if self._is_platform():
            return f"{self._origin()}/v3/memories/search/"
        return f"{self._base_url()}/search"

    def _list_url(self) -> str:
        if self._is_platform():
            return f"{self._origin()}/v3/memories/"
        return f"{self._base_url()}/memories"

    def _delete_url(self, memory_id: str | None = None) -> str:
        if self._is_platform():
            if memory_id is not None:
                return f"{self._origin()}/v1/memories/{memory_id}/"
            return f"{self._origin()}/v1/memories/"
        if memory_id is not None:
            return f"{self._base_url()}/memories/{memory_id}"
        return f"{self._base_url()}/memories"

    def _get_url(self, memory_id: str) -> str:
        return self._delete_url(memory_id)

    async def add_memories(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """写入记忆：Platform ``POST /v3/memories/add/``，OSS ``POST /memories``。

        异步 fire-and-forget 调用，不在 Langfuse 中单独建 trace，避免与 chat-turn
        共用 trace_id 时产生第二条 root observation。
        """
        if not self._mem0_enabled():
            return
        url = self._add_url()
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

    @staticmethod
    def _visibility_flags(
        governance_status: MemoryGovernanceStatus | None,
    ) -> dict[str, bool]:
        flags: dict[str, bool] = {}
        if governance_status == "active":
            flags["latest_only"] = True
        elif governance_status in ("merged", "archived"):
            flags["include_merged"] = True
        return flags

    @staticmethod
    def _build_filters(
        user_id: str,
        *,
        governance_status: MemoryGovernanceStatus | None = None,
        memory_kind: MemoryKindQuery | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> dict[str, Any]:
        """Build Mem0 search/list filters. Extra conditions use AND."""
        extra: list[dict[str, Any]] = []
        if governance_status is not None and governance_status != "active":
            extra.append({"governance_status": governance_status})
        if memory_kind == "pattern":
            extra.append({"memory_kind": "pattern"})
        elif memory_kind == "ordinary":
            extra.append({"memory_kind": {"ne": "pattern"}})
        if created_from is not None or created_to is not None:
            created: dict[str, str] = {}
            if created_from is not None:
                created["gte"] = created_from
            if created_to is not None:
                created["lte"] = created_to
            extra.append({"created_at": created})
        if not extra:
            return {"user_id": user_id}
        return {"AND": [{"user_id": user_id}, *extra]}

    async def search(
        self,
        query: str,
        user_id: str,
        threshold: float | None = None,
        limit: int | None = None,
        governance_status: MemoryGovernanceStatus | None = None,
        memory_kind: MemoryKindQuery | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[MemoryListItem]:
        """搜索记忆：Platform ``POST /v3/memories/search/``，OSS ``POST /search``。"""
        if not self._mem0_enabled():
            return []
        url = self._search_url()
        limit = limit if limit is not None else self.config.search_limit
        body: dict[str, Any] = {
            "query": query,
            "filters": self._build_filters(
                user_id,
                governance_status=governance_status,
                memory_kind=memory_kind,
                created_from=created_from,
                created_to=created_to,
            ),
            "top_k": limit,
        }
        body.update(self._visibility_flags(governance_status))
        if threshold is not None:
            body["threshold"] = threshold
        with observation_span(
            "memory-search",
            input={
                "query": query,
                "top_k": limit,
                "threshold": threshold,
            },
        ) as span:
            try:
                async with httpx.AsyncClient(timeout=self._search_timeout) as client:
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

            r = self._parse_memory_items(data)
            r.sort(
                key=lambda x: x.score if x.score is not None else float("-inf"),
                reverse=True,
            )
            r = r[:limit]
            if span is not None:
                span.update(
                    output={
                        "count": len(r),
                        "memories": [item.model_dump(mode="json") for item in r],
                    }
                )
            return r

    async def get_memories(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        governance_status: MemoryGovernanceStatus | None = None,
        memory_kind: MemoryKindQuery | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> MemoryListResponse:
        """获取用户记忆列表（服务端分页）。

        Platform：``POST /v3/memories/?page=&page_size=``（filters 放 body）。
        OSS：``GET /memories?user_id=&page=&page_size=``。
        """
        if not self._mem0_enabled():
            return MemoryListResponse(
                memories=[], total=0, page=page, page_size=page_size
            )
        try:
            if self._is_platform():
                items, total = await self._get_memories_platform(
                    user_id,
                    page=page,
                    page_size=page_size,
                    governance_status=governance_status,
                    memory_kind=memory_kind,
                    created_from=created_from,
                    created_to=created_to,
                )
            else:
                items, total = await self._get_memories_oss(
                    user_id,
                    page=page,
                    page_size=page_size,
                    governance_status=governance_status,
                    memory_kind=memory_kind,
                    created_from=created_from,
                    created_to=created_to,
                )
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 get_memories failed",
                user_id=user_id,
                error=e,
            )
            return MemoryListResponse(
                memories=[], total=0, page=page, page_size=page_size
            )
        items.sort(key=lambda x: x.created_at, reverse=True)
        return MemoryListResponse(
            memories=items, total=total, page=page, page_size=page_size
        )

    async def get_memory(self, memory_id: str) -> MemoryListItem | None:
        """按 id 查询单条记忆。

        Platform：``GET /v1/memories/{id}/``。
        OSS：``GET /memories/{id}``。
        不存在时返回 ``None``。
        """
        if not self._mem0_enabled():
            return None
        url = self._get_url(memory_id)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.warning(
                "Mem0 get_memory failed",
                memory_id=memory_id,
                error=e,
            )
            raise
        return self._parse_memory_item(data)

    async def _get_memories_oss(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        governance_status: MemoryGovernanceStatus | None = None,
        memory_kind: MemoryKindQuery | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> tuple[list[MemoryListItem], int]:
        """OSS 列表：``page`` / ``page_size``，总数取 envelope ``count``。"""
        url = self._list_url()
        params: dict[str, Any] = {
            "user_id": user_id,
            "page": page,
            "page_size": page_size,
        }
        if governance_status is not None and governance_status != "active":
            params["governance_status"] = governance_status
        if memory_kind is not None:
            params["memory_kind"] = memory_kind
        if created_from is not None:
            params["created_from"] = created_from
        if created_to is not None:
            params["created_to"] = created_to
        params.update(self._visibility_flags(governance_status))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        items = self._parse_memory_items(data)
        total = self._parse_list_count(data, fallback=len(items))
        return items, total

    async def _get_memories_platform(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        governance_status: MemoryGovernanceStatus | None = None,
        memory_kind: MemoryKindQuery | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> tuple[list[MemoryListItem], int]:
        url = self._list_url()
        body: dict[str, Any] = {
            "filters": self._build_filters(
                user_id,
                governance_status=governance_status,
                memory_kind=memory_kind,
                created_from=created_from,
                created_to=created_to,
            )
        }
        body.update(self._visibility_flags(governance_status))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                params={"page": page, "page_size": page_size},
                json=body,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        items = self._parse_memory_items(data)
        total = self._parse_list_count(data, fallback=len(items))
        return items, total

    async def delete_memory(self, memory_id: str) -> None:
        """删除单条记忆：Platform ``DELETE /v1/memories/{id}/``，OSS ``DELETE /memories/{id}``。"""
        if not self._mem0_enabled():
            return
        url = self._delete_url(memory_id)
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
        """按 user_id 删除全部记忆：Platform / OSS 均为 ``DELETE .../memories/?user_id=``。"""
        if not self._mem0_enabled():
            return
        url = self._delete_url()
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

    @staticmethod
    def _parse_memory_items(data: object) -> list[MemoryListItem]:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("results"), list):
            items = data["results"]
        else:
            return []
        return [
            MemoryListItem.model_validate(item)
            for item in items
            if isinstance(item, dict)
        ]

    @staticmethod
    def _parse_list_count(data: object, fallback: int) -> int:
        if isinstance(data, dict) and isinstance(data.get("count"), int):
            return data["count"]
        return fallback

    @staticmethod
    def _parse_memory_item(data: object) -> MemoryListItem | None:
        if isinstance(data, dict):
            nested = data.get("memory")
            if isinstance(nested, dict):
                data = nested
            elif isinstance(data.get("results"), list):
                items = MemoryService._parse_memory_items(data)
                return items[0] if items else None
        elif isinstance(data, list):
            items = MemoryService._parse_memory_items(data)
            return items[0] if items else None
        else:
            return None
        if not isinstance(data, dict):
            return None
        try:
            return MemoryListItem.model_validate(data)
        except ValidationError:
            return None

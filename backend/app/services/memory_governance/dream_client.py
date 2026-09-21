"""Mem0 Dream pass 客户端（自建 OSS ``POST /dream`` + 治理所需的读接口）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas.config import MemoryConfig
from app.utils.logger import logger


class DreamBackendUnsupported(RuntimeError):
    """当前 Mem0 后端不支持被外部触发治理 pass。

    Platform 的 Dream 由服务端自行调度，没有对外开放的「跑一次 pass」接口。
    """


class DreamPassError(RuntimeError):
    """Dream／Mem0 治理接口调用失败（非 2xx 或响应体非法）。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Mem0 dream call failed: HTTP {status_code} {detail}")
        self.status_code = status_code
        self.detail = detail


def parse_mem0_datetime(value: Any) -> datetime | None:
    """解析 Mem0 返回的时间字符串（ISO8601，可能带 ``Z``）为 UTC aware datetime。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class DreamClient:
    """调用 Mem0 OSS 的治理接口。

    - ``POST {base_url}/dream``：触发单个用户的治理 pass
    - ``GET  {base_url}/dream``（按 user_id 过滤）：读该用户最近一次 pass → 水位去重
    - ``GET  {base_url}/memories``（按 user_id 过滤）：读记忆条数 → 最小记忆量门槛
    - ``GET  {base_url}/memories``（不带标识符）：全量列表 → 周扫发现候选用户

    路径与鉴权语义与 ``app/services/user/memory_service.py`` 对齐（``X-API-Key`` 头，
    同时带 ``Authorization: Token 前缀 + API Key``，OSS 路径不带尾斜杠）。
    """

    def __init__(self, config: MemoryConfig, *, timeout_s: float = 300.0) -> None:
        self.config = config
        self._timeout = timeout_s

    def _base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def is_platform(self) -> bool:
        parsed = urlparse(self.config.base_url.strip())
        host = (parsed.netloc or "").split("@")[-1].split(":")[0].lower()
        path = (parsed.path or "").rstrip("/")
        return host == "api.mem0.ai" or path.endswith("/v3")

    def enabled(self) -> bool:
        return bool(self.config.base_url.strip()) and bool(self.config.api_key.strip())

    def dream_url(self) -> str:
        return f"{self._base_url()}/dream"

    def memories_url(self) -> str:
        return f"{self._base_url()}/memories"

    def _headers(self) -> dict[str, str]:
        api_key = self.config.api_key.strip()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": api_key,
            "Authorization": f"Token {api_key}",
        }

    def _require_supported(self) -> None:
        if not self.enabled():
            raise DreamBackendUnsupported(
                "memory_config.base_url / api_key 未配置，无法调用 Mem0 治理接口"
            )
        if self.is_platform():
            raise DreamBackendUnsupported(
                "Mem0 Platform 的 Dream 由服务端自行调度，未开放外部触发接口"
            )

    async def _get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=self._headers())
        if resp.status_code >= 400:
            raise DreamPassError(resp.status_code, resp.text[:500])
        try:
            body: Any = resp.json()
        except ValueError as e:
            raise DreamPassError(resp.status_code, f"invalid json response: {e}") from e
        if not isinstance(body, dict):
            raise DreamPassError(resp.status_code, "unexpected response shape")
        return body

    async def run_pass(
        self,
        *,
        user_id: str,
        consolidate: bool = True,
        synthesize: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """触发单个用户的治理 pass，返回 Mem0 的 report（含 ``pass_id`` / ``stats``）。

        Mem0 侧 ``POST /dream`` 要求 ``user_id`` / ``agent_id`` / ``run_id`` 至少一个；
        这里按用户维度调用，全量 pass 的 LLM 成本由 Mem0 侧承担。
        """
        self._require_supported()
        body: dict[str, Any] = {
            "user_id": user_id,
            "consolidate": consolidate,
            "synthesize": synthesize,
            "force": force,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self.dream_url(), json=body, headers=self._headers()
            )
        if resp.status_code >= 400:
            raise DreamPassError(resp.status_code, resp.text[:500])
        try:
            report: Any = resp.json()
        except ValueError as e:
            raise DreamPassError(resp.status_code, f"invalid json response: {e}") from e
        if not isinstance(report, dict):
            raise DreamPassError(resp.status_code, "unexpected response shape")
        logger.info(
            "Mem0 dream pass done",
            user_id=user_id,
            pass_id=report.get("pass_id"),
        )
        return report

    async def last_pass_at(self, user_id: str) -> datetime | None:
        """该用户最近一次 pass 的时间；读不到时返回 ``None``（不做水位跳过）。

        ``GET /dream`` 按 ``created_at`` 倒序，``limit=1`` 即最新一次。
        """
        if not self.enabled() or self.is_platform():
            return None
        try:
            body = await self._get_json(
                self.dream_url(), params={"user_id": user_id, "limit": 1}
            )
        except (DreamPassError, httpx.HTTPError) as e:
            logger.warning("Read Mem0 dream passes failed", user_id=user_id, error=e)
            return None
        results = body.get("results")
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        if not isinstance(first, dict):
            return None
        return parse_mem0_datetime(first.get("created_at"))

    async def memory_count(self, user_id: str) -> int | None:
        """该用户的记忆条数；读不到时返回 ``None``（不做门槛判断）。

        ``GET /memories`` 按 user_id 过滤时响应形如 ``{"results": [...], "count": N}``；
        ``count`` 缺失时退化为按 ``page_size=1`` 的单页结果判断。
        """
        if not self.enabled() or self.is_platform():
            return None
        try:
            body = await self._get_json(
                self.memories_url(),
                params={"user_id": user_id, "page": 1, "page_size": 1},
            )
        except (DreamPassError, httpx.HTTPError) as e:
            logger.warning("Read Mem0 memory count failed", user_id=user_id, error=e)
            return None
        count = body.get("count")
        if isinstance(count, int):
            return count
        results = body.get("results")
        if isinstance(results, list):
            return len(results)
        return None

    async def list_memory_user_ids(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 50,
        max_users: int | None = None,
    ) -> list[str]:
        """翻页读取全量记忆列表，去重后返回拥有记忆的 ``user_id``（周扫用）。

        ``GET /memories`` 不带标识符是 admin 级接口：需要 ``ADMIN_API_KEY``、
        ``AUTH_DISABLED`` 或 admin 角色凭证（``mem0/server/main.py`` 的
        ``get_all_memories``），否则 Mem0 返回 403 → 抛 ``DreamPassError``，
        由调用方决定降级策略。
        """
        self._require_supported()
        user_ids: list[str] = []
        seen: set[str] = set()
        pages_read = 0
        for page in range(1, max_pages + 1):
            body = await self._get_json(
                self.memories_url(), params={"page": page, "page_size": page_size}
            )
            pages_read = page
            results = body.get("results")
            if not isinstance(results, list) or not results:
                break
            for row in results:
                if not isinstance(row, dict):
                    continue
                user_id = row.get("user_id")
                if not isinstance(user_id, str) or not user_id or user_id in seen:
                    continue
                seen.add(user_id)
                user_ids.append(user_id)
                if max_users is not None and len(user_ids) >= max_users:
                    logger.info(
                        "Mem0 memory user scan truncation",
                        scanned_pages=pages_read,
                        users=len(user_ids),
                    )
                    return user_ids
            if len(results) < page_size:
                break
        logger.info(
            "Mem0 memory user scan done",
            scanned_pages=pages_read,
            users=len(user_ids),
        )
        return user_ids

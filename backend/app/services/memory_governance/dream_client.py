"""Mem0 Dream pass 客户端（自建 OSS ``POST /dream`` + 治理所需的读接口）。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas.config import MemoryConfig
from app.utils.logger import logger

# 水位只需要「最新一条全量 pass」这一行：服务端已支持 ``?source=manual,scheduler`` 过滤
# （``WHERE source IN (...) ORDER BY created_at DESC``），所以 ``limit=1`` 就是答案，
# 不必拉一页回来自己筛。
_WATERMARK_SCAN_LIMIT = 1

# 本 Worker 触发的全量 pass 在 Mem0 里打的来源标签（``POST /dream`` 的 ``source`` 入参，
# 服务端 ``normalize_pass_source`` 会去空白/转小写）。有了它，就能把「定时任务跑的」
# 与「人工 curl 跑的」在全量 pass 记录里分开，排查成本时有据可查。
_WORKER_PASS_SOURCE = "scheduler"

# 算作「已完成全量治理」的来源集合 = 任何真正跑过全量 pass 的渠道。
# 客户端据此逐行核对 ``source``（服务端不支持 ``source`` 过滤时的兜底路径）；
# 请求里也会把它们拼成 ``source=manual,scheduler`` 下推到服务端 SQL。
_FULL_PASS_SOURCES = ("manual", _WORKER_PASS_SOURCE)

# 「全量 pass」的来源值：``POST /dream`` 的默认标签是 ``source="manual"``
# （mem0 ``server/governance/engine.py`` 的 ``normalize_pass_source``）。写记忆触发的
# ``source="on_add"`` 是轻量 consolidate（``engine.py`` 的 ``run_on_add``：只
# merge/supersede，不做 synthesis），**不代表治理已跑过**，必须排除——否则活跃用户每写
# 一条记忆就把当天的全量 pass 顶掉。


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


def _pick_full_pass(rows: Iterable[Any]) -> datetime | None:
    """按返回顺序（``created_at`` 倒序）挑第一条「全量 pass」的 ``created_at``。

    逐行核对 ``source``：只认 ``_FULL_PASS_SOURCES``；非 dict、缺 ``source``、时间解析
    失败的行都跳过并继续往下看（服务端已过滤时这些分支都不会命中，留着是为了旧服务）。
    """
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "").lower() not in _FULL_PASS_SOURCES:
            continue
        parsed = parse_mem0_datetime(row.get("created_at"))
        if parsed is not None:
            return parsed
    return None


class DreamClient:
    """调用 Mem0 OSS 的治理接口。

    - ``POST {base_url}/dream``：触发单个用户的治理 pass（带 ``source=scheduler`` 标签）
    - ``GET  {base_url}/dream``（按 user_id 过滤）：读该用户最近一次**全量** pass →
      水位去重（``source="on_add"`` 的轻量 consolidate 不算，见 ``last_full_pass_at``）
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
        ``source`` 固定打成本 Worker 的标签（``scheduler``），这样水位查询能把它与人工
        ``curl`` 跑的全量 pass 一起认作「已治理」，同时又能按来源分开排查。
        """
        self._require_supported()
        body: dict[str, Any] = {
            "user_id": user_id,
            "consolidate": consolidate,
            "synthesize": synthesize,
            "force": force,
            "source": _WORKER_PASS_SOURCE,
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

    async def last_full_pass_at(self, user_id: str) -> datetime | None:
        """该用户最近一次**全量** pass 的时间；读不到时返回 ``None``（不做水位跳过）。

        ``GET /dream`` 按 ``created_at`` 倒序返回 pass 记录，其中 ``source="on_add"`` 是
        「写记忆时触发的轻量 consolidate」（只 merge/supersede，不做 synthesis），**不能**
        算作已完成治理——否则活跃用户每写一条记忆就把当天的全量 pass 顶掉，日跑对他们永远
        跳过（实测：dev 上两位用户的历史 pass 全是/大多是 on_add，其中一位累计 733 条记忆）。

        请求带 ``source=manual,scheduler`` + ``limit=1``，服务端在 SQL 层过滤后返回的就是
        最新一条全量 pass，一次请求拿到答案。返回行仍逐行核对 ``source``：这层不是为兼容
        旧服务，而是保证**失败方向安全**——万一拿到的是 on_add（服务端异常/代理吞掉参数），
        宁可返回 ``None`` 放行（多花一次 pass 的钱），也不要把 on_add 认成「已治理」而
        永久跳过该用户。
        """
        if not self.enabled() or self.is_platform():
            return None
        try:
            body = await self._get_json(
                self.dream_url(),
                params={
                    "user_id": user_id,
                    "source": ",".join(_FULL_PASS_SOURCES),
                    "limit": _WATERMARK_SCAN_LIMIT,
                },
            )
        except (DreamPassError, httpx.HTTPError) as e:
            logger.warning("Read Mem0 dream passes failed", user_id=user_id, error=e)
            return None
        results = body.get("results")
        if not isinstance(results, list):
            return None
        return _pick_full_pass(results)

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

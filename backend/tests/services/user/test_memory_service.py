"""MemoryService：商业版 Platform v3 与自建 OSS 路径分流。"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.schemas.config import MemoryConfig
from app.services.user.memory_service import MemoryService


def _platform() -> MemoryService:
    return MemoryService(
        MemoryConfig(base_url="https://api.mem0.ai/v3", api_key="m0-test")
    )


def _oss() -> MemoryService:
    return MemoryService(
        MemoryConfig(base_url="http://127.0.0.1:8888", api_key="oss-key")
    )


def _install_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Any
) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(wrapped)
    orig = httpx.AsyncClient

    def fake_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    return seen


def test_platform_urls_use_v3_add_search_and_v1_delete() -> None:
    svc = _platform()
    assert svc._add_url() == "https://api.mem0.ai/v3/memories/add/"
    assert svc._search_url() == "https://api.mem0.ai/v3/memories/search/"
    assert svc._list_url() == "https://api.mem0.ai/v3/memories/"
    assert svc._delete_url("abc") == "https://api.mem0.ai/v1/memories/abc/"
    assert svc._delete_url() == "https://api.mem0.ai/v1/memories/"


def test_oss_urls_keep_legacy_paths() -> None:
    svc = _oss()
    assert svc._add_url() == "http://127.0.0.1:8888/memories"
    assert svc._search_url() == "http://127.0.0.1:8888/search"
    assert svc._list_url() == "http://127.0.0.1:8888/memories"
    assert svc._delete_url("abc") == "http://127.0.0.1:8888/memories/abc"
    assert svc._delete_url() == "http://127.0.0.1:8888/memories"


def test_platform_host_without_v3_suffix_still_detected() -> None:
    svc = MemoryService(
        MemoryConfig(base_url="https://api.mem0.ai", api_key="m0-test")
    )
    assert svc._is_platform()
    assert svc._add_url() == "https://api.mem0.ai/v3/memories/add/"


@pytest.mark.asyncio
async def test_platform_add_posts_to_v3_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.mem0.ai/v3/memories/add/"
        assert request.headers["authorization"] == "Token m0-test"
        body = json.loads(request.content)
        assert body["user_id"] == "u1"
        assert body["messages"][0]["content"] == "hi"
        return httpx.Response(200, json={"event_id": "e1", "status": "PENDING"})

    _install_transport(monkeypatch, handler)
    await _platform().add_memories(
        [{"role": "user", "content": "hi"}],
        user_id="u1",
    )


@pytest.mark.asyncio
async def test_platform_search_posts_to_v3_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.mem0.ai/v3/memories/search/"
        body = json.loads(request.content)
        assert body == {
            "query": "diet",
            "filters": {"user_id": "u1"},
            "top_k": 5,
            "threshold": 0.1,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "m1",
                        "memory": "User is vegetarian",
                        "created_at": "2026-01-15T10:30:00Z",
                        "score": 0.9,
                    }
                ]
            },
        )

    _install_transport(monkeypatch, handler)
    items = await _platform().search("diet", user_id="u1", threshold=0.1)
    assert len(items) == 1
    assert items[0].memory == "User is vegetarian"


@pytest.mark.asyncio
async def test_platform_list_posts_filters_and_paginates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v3/memories/"
        page = int(request.url.params["page"])
        pages.append(page)
        body = json.loads(request.content)
        assert body == {"filters": {"user_id": "u1"}}
        if page == 1:
            return httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": "https://api.mem0.ai/v3/memories/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": "m1",
                            "memory": "first",
                            "created_at": "2026-01-02T00:00:00Z",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "count": 2,
                "next": None,
                "previous": "https://api.mem0.ai/v3/memories/?page=1",
                "results": [
                    {
                        "id": "m2",
                        "memory": "second",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )

    _install_transport(monkeypatch, handler)
    items = await _platform().get_memories("u1")
    assert pages == [1, 2]
    assert [i.id for i in items] == ["m1", "m2"]


@pytest.mark.asyncio
async def test_oss_add_still_posts_legacy_memories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _install_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"ok": True}),
    )
    await _oss().add_memories(
        [{"role": "user", "content": "hi"}],
        user_id="u1",
    )
    assert str(seen[0].url) == "http://127.0.0.1:8888/memories"


@pytest.mark.asyncio
async def test_platform_delete_uses_v1_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _install_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"message": "ok"}),
    )
    await _platform().delete_memory("abc-id")
    assert seen[0].method == "DELETE"
    assert str(seen[0].url) == "https://api.mem0.ai/v1/memories/abc-id/"

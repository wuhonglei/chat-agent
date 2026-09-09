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
    assert svc._get_url("abc") == "https://api.mem0.ai/v1/memories/abc/"


def test_oss_urls_keep_legacy_paths() -> None:
    svc = _oss()
    assert svc._add_url() == "http://127.0.0.1:8888/memories"
    assert svc._search_url() == "http://127.0.0.1:8888/search"
    assert svc._list_url() == "http://127.0.0.1:8888/memories"
    assert svc._delete_url("abc") == "http://127.0.0.1:8888/memories/abc"
    assert svc._delete_url() == "http://127.0.0.1:8888/memories"
    assert svc._get_url("abc") == "http://127.0.0.1:8888/memories/abc"


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
async def test_platform_list_posts_single_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "POST"
        assert request.url.path == "/v3/memories/"
        assert request.url.params["page"] == "2"
        assert request.url.params["page_size"] == "20"
        body = json.loads(request.content)
        assert body == {"filters": {"user_id": "u1"}}
        return httpx.Response(
            200,
            json={
                "count": 41,
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
    payload = await _platform().get_memories("u1", page=2, page_size=20)
    assert len(seen) == 1
    assert payload.total == 41
    assert payload.page == 2
    assert payload.page_size == 20
    assert [i.id for i in payload.memories] == ["m2"]


@pytest.mark.asyncio
async def test_oss_list_forwards_page_and_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == "/memories"
        assert request.url.params["user_id"] == "u1"
        assert request.url.params["page"] == "3"
        assert request.url.params["page_size"] == "10"
        assert "top_k" not in request.url.params
        return httpx.Response(
            200,
            json={
                "count": 25,
                "results": [
                    {
                        "id": "m-oss",
                        "memory": "oss fact",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )

    _install_transport(monkeypatch, handler)
    payload = await _oss().get_memories("u1", page=3, page_size=10)
    assert len(seen) == 1
    assert payload.total == 25
    assert payload.page == 3
    assert payload.page_size == 10
    assert payload.memories[0].id == "m-oss"


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


@pytest.mark.asyncio
async def test_platform_get_memory_uses_v1_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.mem0.ai/v1/memories/abc-id/"
        return httpx.Response(
            200,
            json={
                "id": "abc-id",
                "memory": "User prefers tea",
                "created_at": "2026-01-15T10:30:00Z",
                "user_id": "u1",
                "governance_status": "active",
            },
        )

    _install_transport(monkeypatch, handler)
    item = await _platform().get_memory("abc-id")
    assert item is not None
    assert item.id == "abc-id"
    assert item.memory == "User prefers tea"
    assert item.user_id == "u1"


@pytest.mark.asyncio
async def test_oss_get_memory_uses_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "id": "m-oss",
                "memory": "oss fact",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ),
    )
    item = await _oss().get_memory("m-oss")
    assert seen[0].method == "GET"
    assert str(seen[0].url) == "http://127.0.0.1:8888/memories/m-oss"
    assert item is not None
    assert item.memory == "oss fact"


@pytest.mark.asyncio
async def test_get_memory_returns_none_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport(
        monkeypatch,
        lambda request: httpx.Response(404, json={"error": "Memory not found"}),
    )
    item = await _platform().get_memory("missing-id")
    assert item is None


def test_parse_memory_item_single_object() -> None:
    item = MemoryService._parse_memory_item(
        {
            "id": "m1",
            "memory": "single",
            "created_at": "2026-01-01T00:00:00Z",
            "superseded_by": "newer",
        }
    )
    assert item is not None
    assert item.id == "m1"
    assert item.superseded_by == "newer"


def test_parse_memory_item_nested_memory_object() -> None:
    item = MemoryService._parse_memory_item(
        {
            "memory": {
                "id": "m2",
                "memory": "nested",
                "created_at": "2026-01-01T00:00:00Z",
            }
        }
    )
    assert item is not None
    assert item.id == "m2"
    assert item.memory == "nested"


def test_parse_memory_items_governance_fields() -> None:
    payload = {
        "id": "12d4a00a-4183-47e6-8a8d-4c290d66ea43",
        "memory": "pattern text",
        "hash": "f7c8294ad04047976fa1a54a79eb912c",
        "metadata": None,
        "created_at": "2026-09-08T10:19:03.082200+00:00",
        "updated_at": "2026-09-08T10:19:03.082200+00:00",
        "user_id": "808e0b14-c5ca-4dc1-a495-92ef681eddef",
        "role": "user",
        "governance_status": "active",
        "synthesized_from": ["e8821d1a-7c08-47a7-9d0b-d2454e775589"],
        "memory_kind": "pattern",
        "governance_pass_id": "pass-20260908T101131-437de1fa",
        "governance_timestamp": "2026-09-08T10:19:02.974161+00:00",
        "synthesis_evidence_hash": "0c2500e5e54f0dc5bce810cf91f13fe61cc48904",
        "text_lemmatized": "ignored extra",
    }
    items = MemoryService._parse_memory_items([payload])
    assert len(items) == 1
    item = items[0]
    assert item.memory_kind == "pattern"
    assert item.governance_status == "active"
    assert item.synthesized_from == ["e8821d1a-7c08-47a7-9d0b-d2454e775589"]
    assert item.role == "user"
    assert not hasattr(item, "text_lemmatized")


def test_parse_memory_items_merged_and_superseded_links() -> None:
    items = MemoryService._parse_memory_items(
        [
            {
                "id": "old",
                "memory": "old fact",
                "created_at": "2026-01-01T00:00:00Z",
                "governance_status": "merged",
                "merged_into": "canonical",
            },
            {
                "id": "stale",
                "memory": "stale fact",
                "created_at": "2026-01-02T00:00:00Z",
                "governance_status": "superseded",
                "superseded_by": "newer",
            },
        ]
    )
    assert items[0].merged_into == "canonical"
    assert items[1].superseded_by == "newer"

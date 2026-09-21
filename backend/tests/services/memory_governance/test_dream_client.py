"""DreamClient：Mem0 OSS ``POST /dream`` 的路径、鉴权与错误语义。"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.schemas.config import MemoryConfig
from app.services.memory_governance.dream_client import (
    DreamBackendUnsupported,
    DreamClient,
    DreamPassError,
)


def _oss() -> DreamClient:
    return DreamClient(
        MemoryConfig(base_url="http://127.0.0.1:8888", api_key="oss-key"),
        timeout_s=5.0,
    )


def _platform() -> DreamClient:
    return DreamClient(
        MemoryConfig(base_url="https://api.mem0.ai/v3", api_key="m0-test")
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


def test_oss_url_and_platform_detection() -> None:
    assert _oss().dream_url() == "http://127.0.0.1:8888/dream"
    assert _oss().enabled()
    assert not _oss().is_platform()
    # base_url 尾斜杠不应产生双斜杠
    client = DreamClient(MemoryConfig(base_url="http://127.0.0.1:8888/", api_key="k"))
    assert client.dream_url() == "http://127.0.0.1:8888/dream"
    assert _platform().is_platform()


@pytest.mark.asyncio
async def test_run_pass_posts_user_scoped_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://127.0.0.1:8888/dream"
        assert request.headers["x-api-key"] == "oss-key"
        assert request.headers["authorization"] == "Token oss-key"
        body = json.loads(request.content)
        assert body == {
            "user_id": "u1",
            "consolidate": True,
            "synthesize": True,
            "force": False,
        }
        return httpx.Response(
            200, json={"pass_id": "pass-1", "stats": {"merged": 2}, "actions": []}
        )

    seen = _install_transport(monkeypatch, handler)
    report = await _oss().run_pass(user_id="u1")
    assert len(seen) == 1
    assert report["pass_id"] == "pass-1"
    assert report["stats"] == {"merged": 2}


@pytest.mark.asyncio
async def test_run_pass_flags_are_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["consolidate"] is False
        assert body["synthesize"] is False
        assert body["force"] is True
        return httpx.Response(200, json={"pass_id": "pass-2"})

    _install_transport(monkeypatch, handler)
    await _oss().run_pass(user_id="u1", consolidate=False, synthesize=False, force=True)


@pytest.mark.asyncio
async def test_run_pass_raises_on_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="upstream boom")

    _install_transport(monkeypatch, handler)
    with pytest.raises(DreamPassError) as excinfo:
        await _oss().run_pass(user_id="u1")
    assert excinfo.value.status_code == 502
    assert "upstream boom" in excinfo.value.detail


@pytest.mark.asyncio
async def test_run_pass_raises_on_invalid_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    _install_transport(monkeypatch, handler)
    with pytest.raises(DreamPassError):
        await _oss().run_pass(user_id="u1")


@pytest.mark.asyncio
async def test_platform_and_unconfigured_are_unsupported() -> None:
    with pytest.raises(DreamBackendUnsupported):
        await _platform().run_pass(user_id="u1")

    disabled = DreamClient(MemoryConfig(base_url="", api_key=""))
    assert not disabled.enabled()
    with pytest.raises(DreamBackendUnsupported):
        await disabled.run_pass(user_id="u1")


def test_parse_mem0_datetime_handles_z_and_naive() -> None:
    from app.services.memory_governance.dream_client import parse_mem0_datetime

    z = parse_mem0_datetime("2026-09-17T06:06:00Z")
    assert z is not None and z.tzinfo is not None
    assert z.hour == 6

    offset = parse_mem0_datetime("2026-09-17T06:06:00.024420+00:00")
    assert offset is not None and offset.microsecond == 24420

    naive = parse_mem0_datetime("2026-09-17T06:06:00")
    assert naive is not None and naive.tzinfo is not None

    assert parse_mem0_datetime(None) is None
    assert parse_mem0_datetime("") is None
    assert parse_mem0_datetime("not-a-date") is None


@pytest.mark.asyncio
async def test_last_pass_at_reads_latest_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).startswith("http://127.0.0.1:8888/dream?")
        assert request.url.params["user_id"] == "u1"
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"pass_id": "pass-9", "created_at": "2026-09-16T22:00:00+00:00"},
                    {"pass_id": "pass-8", "created_at": "2026-09-15T22:00:00+00:00"},
                ]
            },
        )

    _install_transport(monkeypatch, handler)
    last = await _oss().last_pass_at("u1")
    assert last is not None and last.day == 16


@pytest.mark.asyncio
async def test_last_pass_at_returns_none_when_no_pass_or_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, Any] = {"resp": httpx.Response(200, json={"results": []})}
    _install_transport(monkeypatch, lambda request: state["resp"])

    assert await _oss().last_pass_at("u1") is None

    state["resp"] = httpx.Response(500, text="nope")
    assert await _oss().last_pass_at("u1") is None

    # Platform / 未配置时不发请求，直接不做水位判断
    assert await _platform().last_pass_at("u1") is None
    assert (
        await DreamClient(MemoryConfig(base_url="", api_key="")).last_pass_at("u1")
        is None
    )


@pytest.mark.asyncio
async def test_memory_count_prefers_count_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("http://127.0.0.1:8888/memories?")
        assert request.url.params["user_id"] == "u1"
        assert request.url.params["page_size"] == "1"
        return httpx.Response(200, json={"results": [{"id": "m1"}], "count": 4600})

    _install_transport(monkeypatch, handler)
    assert await _oss().memory_count("u1") == 4600


@pytest.mark.asyncio
async def test_memory_count_falls_back_to_result_len(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, Any] = {
        "resp": httpx.Response(200, json={"results": [{"id": "m1"}]})
    }
    _install_transport(monkeypatch, lambda request: state["resp"])

    assert await _oss().memory_count("u1") == 1

    state["resp"] = httpx.Response(502, text="bad gateway")
    assert await _oss().memory_count("u1") is None


@pytest.mark.asyncio
async def test_list_memory_user_ids_paginates_and_dedupes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages: dict[int, list[dict[str, Any]]] = {
        1: [{"user_id": "a"}, {"user_id": "b"}, {"user_id": "a"}],
        2: [{"user_id": "c"}],
    }
    seen_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        seen_pages.append(page)
        assert request.url.params["page_size"] == "3"
        return httpx.Response(200, json={"results": pages.get(page, [])})

    _install_transport(monkeypatch, handler)
    ids = await _oss().list_memory_user_ids(page_size=3, max_pages=10)
    assert ids == ["a", "b", "c"]
    # 第 2 页不满一页（1 < 3）即判定翻完，不再多请求一次空页
    assert seen_pages == [1, 2]


@pytest.mark.asyncio
async def test_list_memory_user_ids_stops_at_max_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"user_id": "a"}, {"user_id": "b"}, {"user_id": "c"}]},
        )

    _install_transport(monkeypatch, handler)
    ids = await _oss().list_memory_user_ids(page_size=3, max_pages=10, max_users=2)
    assert ids == ["a", "b"]


@pytest.mark.asyncio
async def test_list_memory_user_ids_raises_on_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全量列表是 admin 接口：非 admin 凭证 403 要显式抛错，让上层决定降级。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Admin role required"})

    _install_transport(monkeypatch, handler)
    with pytest.raises(DreamPassError) as excinfo:
        await _oss().list_memory_user_ids(page_size=10, max_pages=1)
    assert excinfo.value.status_code == 403

    with pytest.raises(DreamBackendUnsupported):
        await _platform().list_memory_user_ids()

"""Tests for vision_analyze image loading and model call."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.vision_mcp.analyze import (
    VisionAnalyzeTool,
    fetch_remote_image,
    load_image_data_url,
)
from app.schemas.config import LLMConfig
from app.utils.context import set_request_context
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff" + b"\x00" * 16


@pytest.fixture
def ctx() -> ToolContext:
    set_request_context(user_id="test_user", conversation_id="test_workspace")
    return ToolContext()


@pytest.fixture
def uploads_dir(ctx: ToolContext) -> Path:
    directory = get_paths().sandbox_uploads_dir("test_user", "test_workspace")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _llm_config() -> LLMConfig:
    return LLMConfig(
        api_key="sk-test",
        api_base="https://example.invalid/v1",
        model_name="vision-test",
        context_limit=8192,
        max_output_tokens=1024,
        image_support=True,
    )


def _completion(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, Any],
    ctx: ToolContext,
    *,
    answer: str = "图中是一只猫",
) -> tuple[Any, list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []

    def fake_resolve(name: str) -> LLMConfig:
        assert name == "vision"
        return _llm_config()

    class _FakeService:
        def __init__(self, config: LLMConfig, think_mode: bool = False) -> None:
            assert config.model_name == "vision-test"
            assert think_mode is False
            self.extra_body = {"enable_thinking": False}

        async def call_llm_api(
            self,
            model: str,
            messages: list[dict[str, Any]],
            stream: bool,
            **kwargs: Any,
        ) -> SimpleNamespace:
            captured.append(
                {"model": model, "messages": messages, "stream": stream, **kwargs}
            )
            return _completion(answer)

    monkeypatch.setattr(
        "app.mcp.mcp_servers.vision_mcp.analyze.resolve_scenario",
        fake_resolve,
    )
    monkeypatch.setattr(
        "app.mcp.mcp_servers.vision_mcp.analyze.LLMService",
        _FakeService,
    )
    result = await VisionAnalyzeTool().execute(arguments, ctx)
    return result, captured


def _image_part(captured: list[dict[str, Any]]) -> str:
    content = captured[0]["messages"][1]["content"]
    return str(content[1]["image_url"]["url"])


@pytest.mark.asyncio
async def test_virtual_path_sends_png_and_question(
    ctx: ToolContext, uploads_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = uploads_dir / "shot.png"
    image_path.write_bytes(PNG)
    virtual = f"{vfs_config.uploads_prefix}shot.png"

    result, captured = await _run(
        monkeypatch,
        {"image_url": virtual, "question": "这是什么？"},
        ctx,
    )

    assert result.is_error is False
    assert result.content == "图中是一只猫"
    assert captured[0]["stream"] is False
    assert captured[0]["messages"][1]["content"][0]["text"] == "这是什么？"
    assert _image_part(captured).startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_data_url_is_forwarded(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    encoded = base64.b64encode(JPEG).decode("ascii")
    data_url = f"data:image/jpeg;base64,{encoded}"

    result, captured = await _run(
        monkeypatch,
        {"image_url": data_url, "question": "描述颜色"},
        ctx,
    )

    assert result.is_error is False
    assert _image_part(captured) == data_url


@pytest.mark.asyncio
async def test_http_url_uses_downloaded_bytes(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = f"data:image/png;base64,{base64.b64encode(PNG).decode('ascii')}"

    async def fake_fetch(url: str, *, client: httpx.AsyncClient | None = None) -> str:
        assert url == "https://cdn.example/cat.png"
        assert client is None
        return expected

    monkeypatch.setattr(
        "app.mcp.mcp_servers.vision_mcp.analyze.fetch_remote_image",
        fake_fetch,
    )
    result, captured = await _run(
        monkeypatch,
        {
            "image_url": "https://cdn.example/cat.png",
            "question": "有几只动物？",
        },
        ctx,
    )

    assert result.is_error is False
    assert _image_part(captured) == expected


@pytest.mark.asyncio
async def test_missing_params(ctx: ToolContext) -> None:
    tool = VisionAnalyzeTool()
    missing_url = await tool.execute({"question": "hi"}, ctx)
    missing_question = await tool.execute({"image_url": "data:image/png;base64,AA=="}, ctx)
    assert missing_url.is_error
    assert "image_url" in missing_url.content
    assert missing_question.is_error
    assert "question" in missing_question.content


@pytest.mark.asyncio
async def test_rejects_non_image_and_traversal(
    ctx: ToolContext, uploads_dir: Path
) -> None:
    text_file = uploads_dir / "notes.txt"
    text_file.write_text("hello", encoding="utf-8")
    tool = VisionAnalyzeTool()

    not_image = await tool.execute(
        {
            "image_url": f"{vfs_config.uploads_prefix}notes.txt",
            "question": "读一下",
        },
        ctx,
    )
    traversal = await tool.execute(
        {
            "image_url": f"{vfs_config.uploads_prefix}../secret.png",
            "question": "读一下",
        },
        ctx,
    )
    host_path = await tool.execute(
        {"image_url": "/etc/passwd", "question": "读一下"},
        ctx,
    )

    assert not_image.is_error
    assert "unsupported image type" in not_image.content
    assert traversal.is_error
    assert host_path.is_error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.png",
        "http://10.1.2.3/a.png",
        "http://192.168.1.5/a.png",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/a.png",
        "http://localhost/a.png",
    ],
)
async def test_rejects_non_public_url(url: str) -> None:
    with pytest.raises(ValueError, match="not a public address"):
        await fetch_remote_image(url)


@pytest.mark.asyncio
async def test_rejects_redirect_to_private_address() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "1.1.1.1":
            return httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/secret.png"},
            )
        raise AssertionError(f"unexpected request {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        with pytest.raises(ValueError, match="not a public address"):
            await fetch_remote_image("http://1.1.1.1/cat.png", client=client)


@pytest.mark.asyncio
async def test_fetch_public_png() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "1.1.1.1"
        return httpx.Response(
            200,
            content=PNG,
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        data_url = await fetch_remote_image("https://1.1.1.1/cat.png", client=client)

    assert data_url == f"data:image/png;base64,{base64.b64encode(PNG).decode('ascii')}"


@pytest.mark.asyncio
async def test_data_url_helper_rejects_non_image() -> None:
    with pytest.raises(ValueError, match="unsupported image type"):
        await load_image_data_url(
            "data:text/plain;base64,aGVsbG8=",
            user_id="u",
            conversation_id="c",
        )

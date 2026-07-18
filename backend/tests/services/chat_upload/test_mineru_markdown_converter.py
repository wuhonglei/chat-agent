"""MinerUMarkdownConverter 单元测试（mock HTTP + ZIP）。"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from app.schemas.config import MinerUConfig
from app.services.chat_upload.mineru_markdown_converter import (
    MinerUMarkdownConversionError,
    MinerUMarkdownConverter,
)


def _build_result_zip(
    *,
    md_text: str,
    images: dict[str, bytes] | None = None,
    content_list_v2: list | None = None,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("document.md", md_text)
        if images:
            for name, data in images.items():
                zf.writestr(f"images/{name}", data)
        if content_list_v2 is not None:
            zf.writestr(
                "document_content_list_v2.json",
                json.dumps(content_list_v2),
            )
    return buf.getvalue()


def _make_handler(
    *,
    zip_bytes: bytes,
    poll_states: list[str] | None = None,
) -> httpx.MockTransport:
    states = list(poll_states or ["done"])
    poll_idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/v4/file-urls/batch") and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/put"],
                    },
                },
            )
        if (
            str(request.url).startswith("https://upload.example/put")
            and request.method == "PUT"
        ):
            return httpx.Response(200, content=b"ok")
        if "/api/v4/extract-results/batch/" in path and request.method == "GET":
            idx = min(poll_idx["i"], len(states) - 1)
            poll_idx["i"] += 1
            state = states[idx]
            item: dict = {"state": state}
            if state == "done":
                item["full_zip_url"] = "https://download.example/result.zip"
            elif state == "failed":
                item["err_msg"] = "boom"
            return httpx.Response(
                200,
                json={"code": 0, "msg": "ok", "data": {"extract_result": [item]}},
            )
        if str(request.url).startswith("https://download.example/result.zip"):
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(404, text=f"unexpected: {request.method} {request.url}")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_convert_writes_md_and_merges_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_bytes = _build_result_zip(
        md_text="Hello\n\n![](images/a.png)\n",
        images={"a.png": b"png-bytes"},
        content_list_v2=[
            [
                {
                    "type": "image",
                    "sub_type": "figure",
                    "content": {"image_source": {"path": "images/a.png"}},
                }
            ]
        ],
    )
    transport = _make_handler(zip_bytes=zip_bytes)

    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    src = tmp_path / "report.pdf"
    src.write_bytes(b"%PDF-1.4 mock")
    md_path = tmp_path / "derived" / "report.md"
    images_dir = tmp_path / "derived" / "images"

    cfg = MinerUConfig(
        enabled=True,
        api_url="https://mineru.net",
        api_key="test-key",
        model_version="vlm",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=5.0,
    )
    converter = MinerUMarkdownConverter(config=cfg)
    md_text = await converter.convert_to_markdown(
        src, md_path=md_path, images_dir=images_dir
    )

    assert md_path.is_file()
    assert "![插图](images/a.png)" in md_text
    assert (images_dir / "a.png").read_bytes() == b"png-bytes"


@pytest.mark.asyncio
async def test_image_name_conflict_renames_and_rewrites_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_bytes = _build_result_zip(
        md_text="![](images/a.png)\n",
        images={"a.png": b"new-bytes"},
    )
    transport = _make_handler(zip_bytes=zip_bytes)
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4")
    md_path = tmp_path / "derived" / "doc.md"
    images_dir = tmp_path / "derived" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "a.png").write_bytes(b"old-bytes")

    cfg = MinerUConfig(
        api_key="test-key",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=5.0,
    )
    converter = MinerUMarkdownConverter(config=cfg)
    md_text = await converter.convert_to_markdown(
        src, md_path=md_path, images_dir=images_dir
    )

    assert (images_dir / "a.png").read_bytes() == b"old-bytes"
    assert (images_dir / "doc_a.png").read_bytes() == b"new-bytes"
    assert "images/doc_a.png" in md_text


@pytest.mark.asyncio
async def test_missing_api_key_raises() -> None:
    converter = MinerUMarkdownConverter(config=MinerUConfig(enabled=True, api_key=""))
    with pytest.raises(MinerUMarkdownConversionError, match="api_key"):
        await converter.convert_to_markdown(
            Path("x.pdf"),
            md_path=Path("x.md"),
            images_dir=Path("images"),
        )


@pytest.mark.asyncio
async def test_poll_failed_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_bytes = _build_result_zip(md_text="# empty\n")
    transport = _make_handler(zip_bytes=zip_bytes, poll_states=["failed"])
    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF-1.4")
    cfg = MinerUConfig(
        api_key="k",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=5.0,
    )
    converter = MinerUMarkdownConverter(config=cfg)
    with pytest.raises(MinerUMarkdownConversionError, match="解析失败"):
        await converter.convert_to_markdown(
            src,
            md_path=tmp_path / "derived" / "a.md",
            images_dir=tmp_path / "derived" / "images",
        )

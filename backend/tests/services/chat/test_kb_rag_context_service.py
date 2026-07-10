"""KbRagContextService 按附件分流单测。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.chat import MarkdownBlock, PdfBlock, TextBlock, TextFileBlock
from app.schemas.config import KbFileRagConfig
from app.services.chat.kb_rag_context_service import (
    KbRagContextService,
    RetrievedChunk,
)


class _FakeEmbedding:
    async def aembed_query(self, text: str) -> list[float]:
        return [0.1] * 1024


def _service(*, short_doc_max_tokens: int = 100) -> KbRagContextService:
    return KbRagContextService(
        rag_config=KbFileRagConfig(
            short_doc_max_tokens=short_doc_max_tokens,
            retrieval_top_k=3,
        ),
        embedding_service=_FakeEmbedding(),
    )


def _md_block(
    *,
    content_id: str = "cid-md",
    token_size: int | None = 10,
    storage_key: str = "conv/doc.md",
) -> MarkdownBlock:
    return MarkdownBlock(
        id=content_id,
        type="markdown",
        url="/api/file/preview/u/doc.md",
        storage_key=storage_key,
        name="doc.md",
        size=100,
        token_size=token_size,
        mime="text/markdown",
    )


@pytest.mark.asyncio
async def test_empty_query_returns_none() -> None:
    service = _service()
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="   ",
        content_blocks=[_md_block()],
    )
    assert result is None


@pytest.mark.asyncio
async def test_no_eligible_attachments_returns_none() -> None:
    service = _service()
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="hello",
        content_blocks=[TextBlock(id="t1", text="hi")],
    )
    assert result is None


@pytest.mark.asyncio
async def test_short_doc_injects_full_text_without_indexing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_key = "conv/short.md"
    file_path = tmp_path / "short.md"
    file_path.write_text("# short content", encoding="utf-8")

    ensure_mock = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        ensure_mock,
    )
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        lambda _uid, _key: file_path,
    )

    service = _service(short_doc_max_tokens=100)
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="总结一下",
        content_blocks=[_md_block(token_size=20, storage_key=storage_key)],
    )

    assert result is not None
    assert len(result) == 1
    assert result[0].content == "# short content"
    ensure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_large_doc_indexes_then_searches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "large.md"
    file_path.write_text("# large " + ("x" * 200), encoding="utf-8")

    ensure_mock = AsyncMock(return_value=5)
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        ensure_mock,
    )
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        lambda _uid, _key: file_path,
    )

    service = _service(short_doc_max_tokens=10)
    chunks = [
        RetrievedChunk(
            content_id="cid-md",
            chunk_idx=0,
            chunk_content="chunk-a",
            distance=0.1,
            metadata_json={"file_name": "large.md"},
        ),
        RetrievedChunk(
            content_id="cid-md",
            chunk_idx=1,
            chunk_content="chunk-b",
            distance=0.2,
            metadata_json={"file_name": "large.md"},
        ),
    ]
    monkeypatch.setattr(
        service,
        "_search_top_k_chunks",
        MagicMock(return_value=chunks),
    )

    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="提取要点",
        content_blocks=[_md_block(token_size=500, storage_key="conv/large.md")],
    )

    assert result is not None
    assert len(result) == 1
    assert "chunk-a" in result[0].content
    assert "chunk-b" in result[0].content
    ensure_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_large_doc_skips_reindex_when_already_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "large.md"
    file_path.write_text("already indexed body", encoding="utf-8")

    ensure_mock = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        ensure_mock,
    )
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        lambda _uid, _key: file_path,
    )

    service = _service(short_doc_max_tokens=5)
    monkeypatch.setattr(
        service,
        "_search_top_k_chunks",
        MagicMock(
            return_value=[
                RetrievedChunk(
                    content_id="cid-md",
                    chunk_idx=0,
                    chunk_content="hit",
                    distance=0.05,
                    metadata_json={"file_name": "large.md"},
                )
            ]
        ),
    )

    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="query",
        content_blocks=[_md_block(token_size=100, storage_key="conv/large.md")],
    )
    assert result is not None
    assert result[0].content == "hit"
    ensure_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_token_size_lazy_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "legacy.md"
    file_path.write_text("legacy full text", encoding="utf-8")

    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        lambda _uid, _key: file_path,
    )
    count_mock = MagicMock(return_value=8)
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.count_attachment_token_size",
        count_mock,
    )
    ensure_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        ensure_mock,
    )

    service = _service(short_doc_max_tokens=100)
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="hello",
        content_blocks=[_md_block(token_size=None, storage_key="conv/legacy.md")],
    )

    assert result is not None
    assert result[0].content == "legacy full text"
    count_mock.assert_called_once()
    ensure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_short_and_large_attachments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    short_path = tmp_path / "short.md"
    short_path.write_text("short body", encoding="utf-8")
    large_path = tmp_path / "large.txt"
    large_path.write_text("large body", encoding="utf-8")

    def _resolve(_uid: str, key: str) -> Path | None:
        if key.endswith("short.md"):
            return short_path
        if key.endswith("large.txt"):
            return large_path
        return None

    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        _resolve,
    )
    ensure_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        ensure_mock,
    )

    service = _service(short_doc_max_tokens=50)
    monkeypatch.setattr(
        service,
        "_search_top_k_chunks",
        MagicMock(
            return_value=[
                RetrievedChunk(
                    content_id="cid-large",
                    chunk_idx=0,
                    chunk_content="large-chunk",
                    distance=0.1,
                    metadata_json={"file_name": "large.txt"},
                )
            ]
        ),
    )

    blocks: list[Any] = [
        MarkdownBlock(
            id="cid-short",
            type="markdown",
            url="/u/short.md",
            storage_key="conv/short.md",
            name="short.md",
            size=10,
            token_size=10,
            mime="text/markdown",
        ),
        TextFileBlock(
            id="cid-large",
            type="text_file",
            url="/u/large.txt",
            storage_key="conv/large.txt",
            name="large.txt",
            size=1000,
            token_size=500,
            mime="text/plain",
        ),
    ]
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="compare",
        content_blocks=blocks,
    )
    assert result is not None
    assert len(result) == 2
    assert result[0].content == "short body"
    assert result[1].content == "large-chunk"
    ensure_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_nested_markdown_is_eligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    md_path = tmp_path / "derived.md"
    md_path.write_text("pdf markdown", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.try_resolve_upload_file_path",
        lambda _uid, _key: md_path,
    )
    monkeypatch.setattr(
        "app.services.chat.kb_rag_context_service.ensure_uploaded_text_chunks_indexed",
        AsyncMock(),
    )

    service = _service(short_doc_max_tokens=1000)
    pdf = PdfBlock(
        id="cid-pdf",
        type="pdf",
        url="/u/a.pdf",
        storage_key="conv/a.pdf",
        name="a.pdf",
        size=200,
        mime="application/pdf",
        markdown=MarkdownBlock(
            id="cid-pdf",
            type="markdown",
            url="/u/derived.md",
            storage_key="conv/derived/a.md",
            derived_from_id="cid-pdf",
            derived_kind="pdf_to_markdown",
            name="a.md",
            size=50,
            token_size=12,
            mime="text/markdown",
        ),
    )
    result = await service.build_context_blocks_for_current_turn(
        user_id="u1",
        query_text="pdf?",
        content_blocks=[pdf],
    )
    assert result is not None
    assert result[0].content == "pdf markdown"

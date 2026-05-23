"""知识库文件分块向量索引服务。"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from langchain_text_splitters import MarkdownTextSplitter
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.kb_file_chunk_embedding_db import KbFileChunkEmbeddingDb
from app.services.base_service.embedding_service import EmbeddingService
from app.utils.logger import logger
from app.utils.token import TokenCalculator


class KbFileChunkIndexingError(RuntimeError):
    """分块向量索引失败。"""


def _split_markdown_text(
    *, text: str, chunk_size: int, chunk_overlap: int
) -> list[str]:
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


async def index_uploaded_text_chunks(
    *,
    user_id: str,
    content_id: str,
    text: str,
    file_name: str,
    source_kind: str,
    text_format: str,
    original_size_bytes: int,
    processed_size_bytes: int,
) -> int:
    """对上传文件文本分块并写入 kb_file_chunk_embeddings。"""
    normalized_text = text.strip()
    if not normalized_text:
        raise KbFileChunkIndexingError("转换后的文本为空，无法生成向量")

    user_id_column = cast(Any, KbFileChunkEmbeddingDb.user_id)
    content_id_column = cast(Any, KbFileChunkEmbeddingDb.content_id)
    with Session(engine) as session:
        existing = session.exec(
            select(KbFileChunkEmbeddingDb)
            .where(user_id_column == user_id, content_id_column == content_id)
            .limit(1)
        ).first()
        if existing is not None:
            logger.info(
                "KB file chunks indexing skipped",
                user_id=user_id,
                content_id=content_id,
                embedding_skipped=True,
            )
            return 0

    rag_cfg = settings.kb_file_rag
    chunks = await asyncio.to_thread(
        _split_markdown_text,
        text=normalized_text,
        chunk_size=rag_cfg.chunk_size,
        chunk_overlap=rag_cfg.chunk_overlap,
    )
    if not chunks:
        raise KbFileChunkIndexingError("分块结果为空，无法生成向量")

    embedding_service = EmbeddingService(settings.embedding_model)
    vectors = await embedding_service.aembed_documents(chunks)
    if not vectors or len(vectors) != len(chunks):
        raise KbFileChunkIndexingError("向量生成失败或向量数量与分块数量不一致")

    token_calculator = TokenCalculator(embedding_service.model_name)
    source_token_count = token_calculator.count_tokens(normalized_text)

    base_metadata: dict[str, Any] = {
        "embedding_model": embedding_service.model_name,
        "embedding_dimension": settings.embedding_model.embedding_dimension,
        "source_kind": source_kind,
        "text_format": text_format,
        "file_name": file_name,
        "source_token_count": source_token_count,
        "original_size_bytes": original_size_bytes,
        "processed_size_bytes": processed_size_bytes,
    }

    try:
        with Session(engine) as session:
            rows = [
                KbFileChunkEmbeddingDb(
                    user_id=user_id,
                    content_id=content_id,
                    chunk_idx=idx,
                    chunk_content=chunk_text,
                    embedding_vector=vectors[idx],
                    metadata_json=base_metadata.copy(),
                )
                for idx, chunk_text in enumerate(chunks)
            ]
            session.add_all(rows)
            session.commit()
    except Exception as exc:
        raise KbFileChunkIndexingError("写入分块向量到数据库失败") from exc

    logger.info(
        "KB file chunks indexed",
        user_id=user_id,
        content_id=content_id,
        chunks_count=len(chunks),
        source_token_count=source_token_count,
        source_kind=source_kind,
        text_format=text_format,
    )
    return len(chunks)

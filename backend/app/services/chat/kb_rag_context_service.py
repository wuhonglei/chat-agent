"""会话内文档 RAG：按当前轮附件逐文件决定全文注入或按需检索。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import bindparam, text

from app.core.db import engine
from app.models.kb_file_chunk_embedding_db import EMBEDDING_DIMENSION
from app.schemas.chat import ContentBlock, KbContextBlock
from app.schemas.config import KbFileRagConfig
from app.services.chat_upload.attachment import try_resolve_upload_file_path
from app.services.chat_upload.kb_chunk_embedding import (
    KbFileChunkIndexingError,
    ensure_uploaded_text_chunks_indexed,
)
from app.services.chat_upload.token_size import count_attachment_token_size
from app.utils.date import get_relative_time_diff
from app.utils.logger import logger
from app.utils.multimodal import (
    RagEligibleAttachment,
    iter_rag_eligible_attachments,
)


@dataclass(frozen=True)
class RetrievedChunk:
    content_id: str
    chunk_idx: int
    chunk_content: str
    distance: float
    metadata_json: dict[str, Any]


class QueryEmbeddingProvider(Protocol):
    async def aembed_query(self, text: str) -> list[float]: ...


class KbRagContextService:
    """基于当前轮附件构建 KB 上下文（短文档全文 / 大文档按需 RAG）。"""

    def __init__(
        self, rag_config: KbFileRagConfig, embedding_service: QueryEmbeddingProvider
    ):
        self.rag_config = rag_config
        self.embedding_service = embedding_service

    async def build_context_blocks_for_current_turn(
        self,
        *,
        user_id: str,
        query_text: str,
        content_blocks: list[ContentBlock],
    ) -> list[KbContextBlock] | None:
        clean_query = query_text.strip()
        if not clean_query:
            return None

        attachments = list(iter_rag_eligible_attachments(content_blocks))
        if not attachments:
            return None

        context_blocks: list[KbContextBlock] = []
        for attachment in attachments:
            try:
                block = await self._build_block_for_attachment(
                    user_id=user_id,
                    query_text=clean_query,
                    attachment=attachment,
                )
            except Exception as exc:
                logger.warning(
                    "Skip attachment KB context due to error",
                    user_id=user_id,
                    content_id=attachment.content_id,
                    error=exc,
                    error_type=type(exc).__name__,
                )
                continue
            if block is not None:
                context_blocks.append(block)

        return context_blocks or None

    async def _build_block_for_attachment(
        self,
        *,
        user_id: str,
        query_text: str,
        attachment: RagEligibleAttachment,
    ) -> KbContextBlock | None:
        file_text = self._read_attachment_text(user_id, attachment)
        if file_text is None:
            return None

        token_size = attachment.token_size
        if token_size is None:
            token_size = count_attachment_token_size(file_text)
            logger.info(
                "Lazy-counted attachment token_size",
                content_id=attachment.content_id,
                token_size=token_size,
            )

        if token_size <= self.rag_config.short_doc_max_tokens:
            return KbContextBlock(
                id=attachment.content_id,
                name=attachment.name,
                created_at=None,
                content=file_text,
            )

        try:
            await ensure_uploaded_text_chunks_indexed(
                user_id=user_id,
                content_id=attachment.content_id,
                text=file_text,
                file_name=attachment.name,
                source_kind=attachment.source_kind,
                text_format=attachment.text_format,
                original_size_bytes=attachment.original_size_bytes,
                processed_size_bytes=attachment.processed_size_bytes,
            )
        except KbFileChunkIndexingError as exc:
            logger.warning(
                "Skip large attachment RAG: indexing failed",
                user_id=user_id,
                content_id=attachment.content_id,
                error=exc,
            )
            return None

        query_vector = await self.embedding_service.aembed_query(query_text)
        if not query_vector:
            logger.info(
                "Skip large attachment RAG: query embedding is empty",
                content_id=attachment.content_id,
            )
            return None
        if len(query_vector) != EMBEDDING_DIMENSION:
            logger.warning(
                "Skip large attachment RAG: embedding dimension mismatch",
                content_id=attachment.content_id,
                actual_dimension=len(query_vector),
                expected_dimension=EMBEDDING_DIMENSION,
            )
            return None

        chunks = await asyncio.to_thread(
            self._search_top_k_chunks,
            user_id,
            [attachment.content_id],
            query_vector,
            self.rag_config.retrieval_top_k,
        )
        if not chunks:
            logger.info(
                "Skip large attachment RAG: no matched chunks",
                content_id=attachment.content_id,
            )
            return None

        return self._chunks_to_context_block(attachment, chunks)

    def _read_attachment_text(
        self,
        user_id: str,
        attachment: RagEligibleAttachment,
    ) -> str | None:
        if not attachment.storage_key:
            logger.warning(
                "Attachment storage_key missing",
                user_id=user_id,
                content_id=attachment.content_id,
            )
            return None
        path: Path | None = try_resolve_upload_file_path(
            user_id, attachment.storage_key
        )
        if path is None:
            logger.warning(
                "Attachment file missing on disk",
                user_id=user_id,
                content_id=attachment.content_id,
                storage_key=attachment.storage_key,
            )
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning(
                "Attachment file read failed",
                user_id=user_id,
                content_id=attachment.content_id,
                path=str(path),
                error=exc,
            )
            return None
        return content or None

    def _chunks_to_context_block(
        self,
        attachment: RagEligibleAttachment,
        chunks: list[RetrievedChunk],
    ) -> KbContextBlock | None:
        first_metadata = chunks[0].metadata_json
        file_name = str(first_metadata.get("file_name") or attachment.name)
        created_at_datetime = self._extract_created_at(first_metadata)
        created_at = get_relative_time_diff(created_at_datetime)

        unique_chunks: dict[int, str] = {}
        for chunk in sorted(chunks, key=lambda item: item.chunk_idx):
            if chunk.chunk_idx not in unique_chunks:
                unique_chunks[chunk.chunk_idx] = chunk.chunk_content.strip()
        merged_chunk_text = "\n\n".join(
            chunk_text for chunk_text in unique_chunks.values() if chunk_text
        ).strip()
        if not merged_chunk_text:
            return None
        return KbContextBlock(
            id=attachment.content_id,
            name=file_name,
            created_at=created_at,
            content=merged_chunk_text,
        )

    def _search_top_k_chunks(
        self,
        user_id: str,
        candidate_content_ids: list[str],
        query_vector: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        vector_literal = self._format_vector_literal(query_vector)
        statement = text(
            """
            SELECT
                content_id,
                chunk_idx,
                chunk_content,
                metadata AS metadata_json,
                (embedding_vector <=> CAST(:query_vector AS vector)) AS distance
            FROM kb_file_chunk_embeddings
            WHERE user_id = :user_id
              AND content_id IN :content_ids
            ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        ).bindparams(bindparam("content_ids", expanding=True))
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    statement,
                    {
                        "user_id": user_id,
                        "content_ids": candidate_content_ids,
                        "query_vector": vector_literal,
                        "top_k": top_k,
                    },
                )
                .mappings()
                .all()
            )
        return [
            RetrievedChunk(
                content_id=str(row["content_id"]),
                chunk_idx=int(row["chunk_idx"]),
                chunk_content=str(row["chunk_content"]),
                distance=float(row["distance"]),
                metadata_json=dict(row.get("metadata_json") or {}),
            )
            for row in rows
        ]

    @staticmethod
    def _extract_created_at(metadata: dict[str, Any]) -> datetime | None:
        raw_value = metadata.get("created_at")
        if isinstance(raw_value, datetime):
            return raw_value
        if not isinstance(raw_value, str):
            return None
        candidate = raw_value.strip()
        if not candidate:
            return None
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    @staticmethod
    def _format_vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(str(value) for value in vector) + "]"

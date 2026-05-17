"""会话内文档 RAG：检索并组装注入到用户侧提示词的 KB 上下文。"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import bindparam, text

from app.core.db import engine
from app.models.kb_file_chunk_embedding_db import EMBEDDING_DIMENSION
from app.schemas.chat import KbContextBlock
from app.schemas.config import KbFileRagConfig
from app.services.chat_upload.attachment import resolve_markdown_path_for_content_id
from app.utils.date import get_relative_time_diff
from app.utils.logger import logger


@dataclass(frozen=True)
class RetrievedChunk:
    file_id: str
    chunk_idx: int
    chunk_content: str
    distance: float
    metadata_json: dict[str, Any]


class QueryEmbeddingProvider(Protocol):
    async def aembed_query(self, text: str) -> list[float]: ...


class KbRagContextService:
    """基于会话内附件 file_id 集合构建 KB 上下文。"""

    def __init__(
        self, rag_config: KbFileRagConfig, embedding_service: QueryEmbeddingProvider
    ):
        self.rag_config = rag_config
        self.embedding_service = embedding_service
        self._force_keyword_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in rag_config.force_rag_keyword_patterns
            if pattern.strip()
        ]

    async def build_context_block_content(
        self,
        *,
        user_id: str,
        query_text: str,
        candidate_file_ids: set[str],
        current_turn_has_attachment: bool,
    ) -> list[KbContextBlock] | None:
        clean_query = query_text.strip()
        if not clean_query:
            return None
        if not candidate_file_ids:
            return None

        query_vector = await self.embedding_service.aembed_query(clean_query)
        if not query_vector:
            logger.info("Skip KB RAG: query embedding is empty")
            return None
        if len(query_vector) != EMBEDDING_DIMENSION:
            logger.warning(
                "Skip KB RAG: embedding dimension mismatch",
                actual_dimension=len(query_vector),
                expected_dimension=EMBEDDING_DIMENSION,
            )
            return None

        chunks = await asyncio.to_thread(
            self._search_top_k_chunks,
            user_id,
            sorted(candidate_file_ids),
            query_vector,
            self.rag_config.retrieval_top_k,
        )
        if not chunks:
            logger.info(
                "Skip KB RAG: no matched chunks",
                candidate_files=len(candidate_file_ids),
            )
            return None

        top_similarity = 1 - chunks[0].distance
        force_rag = current_turn_has_attachment or self._contains_force_keyword(
            clean_query
        )
        if top_similarity < self.rag_config.relevance_score_threshold and not force_rag:
            logger.info(
                "Skip KB RAG: top similarity below threshold",
                top_similarity=top_similarity,
                threshold=self.rag_config.relevance_score_threshold,
            )
            return None

        context_blocks = await asyncio.to_thread(
            self._assemble_context_text,
            user_id,
            chunks,
        )
        if not context_blocks:
            logger.info("Skip KB RAG: assembled context is empty")
            return None
        return context_blocks

    def _contains_force_keyword(self, query_text: str) -> bool:
        return any(
            pattern.search(query_text) for pattern in self._force_keyword_patterns
        )

    def _search_top_k_chunks(
        self,
        user_id: str,
        candidate_file_ids: list[str],
        query_vector: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        vector_literal = self._format_vector_literal(query_vector)
        statement = text(
            """
            SELECT
                file_id,
                chunk_idx,
                chunk_content,
                metadata AS metadata_json,
                (embedding_vector <=> CAST(:query_vector AS vector)) AS distance
            FROM kb_file_chunk_embeddings
            WHERE user_id = :user_id
              AND file_id IN :file_ids
            ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        ).bindparams(bindparam("file_ids", expanding=True))
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    statement,
                    {
                        "user_id": user_id,
                        "file_ids": candidate_file_ids,
                        "query_vector": vector_literal,
                        "top_k": top_k,
                    },
                )
                .mappings()
                .all()
            )
        return [
            RetrievedChunk(
                file_id=str(row["file_id"]),
                chunk_idx=int(row["chunk_idx"]),
                chunk_content=str(row["chunk_content"]),
                distance=float(row["distance"]),
                metadata_json=dict(row.get("metadata_json") or {}),
            )
            for row in rows
        ]

    def _assemble_context_text(
        self, user_id: str, chunks: list[RetrievedChunk]
    ) -> list[KbContextBlock]:
        grouped_chunks: dict[str, list[RetrievedChunk]] = {}
        ordered_file_ids: list[str] = []
        for chunk in chunks:
            if chunk.file_id not in grouped_chunks:
                grouped_chunks[chunk.file_id] = []
                ordered_file_ids.append(chunk.file_id)
            grouped_chunks[chunk.file_id].append(chunk)

        context_blocks: list[KbContextBlock] = []
        for file_id in ordered_file_ids:
            file_chunks = grouped_chunks[file_id]
            first_metadata = file_chunks[0].metadata_json
            file_name = str(first_metadata.get("file_name") or f"{file_id}.md")
            source_token_count = int(first_metadata.get("source_token_count") or 0)
            created_at_datetime = self._extract_created_at(first_metadata)
            created_at = get_relative_time_diff(created_at_datetime)

            full_text: str | None = None
            if source_token_count <= self.rag_config.short_doc_max_tokens:
                full_text = self._read_full_markdown_text(user_id, file_id)

            if full_text:
                context_blocks.append(
                    KbContextBlock(
                        id=file_id,
                        name=file_name,
                        created_at=created_at,
                        content=full_text,
                    )
                )
                continue

            unique_chunks: dict[int, str] = {}
            for chunk in sorted(file_chunks, key=lambda item: item.chunk_idx):
                if chunk.chunk_idx not in unique_chunks:
                    unique_chunks[chunk.chunk_idx] = chunk.chunk_content.strip()
            merged_chunk_text = "\n\n".join(
                text for text in unique_chunks.values() if text
            ).strip()
            if merged_chunk_text:
                context_blocks.append(
                    KbContextBlock(
                        id=file_id,
                        name=file_name,
                        created_at=created_at,
                        content=merged_chunk_text,
                    )
                )

        return context_blocks

    def _read_full_markdown_text(self, user_id: str, file_id: str) -> str | None:
        markdown_path: Path | None = resolve_markdown_path_for_content_id(
            user_id, file_id
        )
        if markdown_path is None:
            logger.warning(
                "KB RAG full markdown missing, fallback to chunks",
                user_id=user_id,
                file_id=file_id,
            )
            return None
        if not markdown_path.is_file():
            logger.warning(
                "KB RAG full markdown missing, fallback to chunks",
                user_id=user_id,
                file_id=file_id,
                markdown_path=str(markdown_path),
            )
            return None
        try:
            content = markdown_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning(
                "KB RAG full markdown read failed, fallback to chunks",
                user_id=user_id,
                file_id=file_id,
                markdown_path=str(markdown_path),
                error=exc,
            )
            return None
        return content or None

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

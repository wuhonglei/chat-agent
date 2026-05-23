from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now

EMBEDDING_DIMENSION = 1024


class KbFileChunkEmbeddingDb(SQLModel, table=True):
    """知识库文件分块向量表"""

    __tablename__ = "kb_file_chunk_embeddings"

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    user_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="用户 ID",
    )
    content_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True),
        description="文件内容 SHA-256",
    )
    chunk_idx: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="分块序号（从 0 开始）",
    )
    chunk_content: str = Field(
        sa_column=Column(Text, nullable=False),
        description="分块文本内容",
    )
    embedding_vector: list[float] = Field(
        sa_column=Column(
            Vector(EMBEDDING_DIMENSION),
            nullable=False,
        ),
        description="分块向量",
    )
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", SQLJSON, nullable=False),
        description="分块元数据",
    )

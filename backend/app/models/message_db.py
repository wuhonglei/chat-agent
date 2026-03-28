from datetime import datetime
from typing import Any, cast

from pgvector.sqlalchemy import Vector
from pydantic import field_serializer
from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlmodel import Field, SQLModel

from app.core.config import settings
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class MessageDb(SQLModel, table=True):
    """消息模型"""

    __tablename__ = "messages"

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    conversation_id: str = Field(
        sa_column=Column(
            String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
        ),
        description="关联对话",
    )
    role: str  # "user" | "assistant"
    content: str = Field(default="", description="Message content")
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        index=True,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True),
    )
    reasoning: str | None = Field(default=None, description="Reasoning content")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, sa_type=SQLJSON, description="Tool calls"
    )
    message_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_type=SQLJSON
    )  # 元数据（模型调用、配置）
    status: str = Field(
        default="pending", description="消息落库状态，pending|done|failed"
    )
    reply_to: str | None = Field(
        default=None, description="关联的用户消息 ID", max_length=36
    )
    tool_calls_duration: float | None = Field(
        default=None, sa_type=Float, description="工具调用耗时（秒）"
    )
    reasoning_duration: float | None = Field(
        default=None, sa_type=Float, description="推理耗时（秒）"
    )
    content_duration: float | None = Field(
        default=None, sa_type=Float, description="内容生成耗时（秒）"
    )
    total_duration: float | None = Field(
        default=None, sa_type=Float, description="总耗时（秒）"
    )
    token_stats: dict[str, Any] | None = Field(
        default=None,
        sa_type=SQLJSON,
        description="Token 使用统计信息（MCP 工具调用、响应生成、标题生成等）",
    )
    embedding_vector: list[float] | None = Field(
        default=None,
        sa_type=Vector(settings.embedding_model.embedding_dimension),
        description="用户消息的 query embedding，用于用户画像语义检索",
    )
    embedding_model: str | None = Field(
        default=None,
        max_length=64,
        description="生成 embedding_vector 的模型名",
    )

    @field_serializer("embedding_vector", when_used="always")
    def serialize_embedding_vector(
        self, value: list[float] | Any
    ) -> list[float] | None:
        """pgvector 从 DB 读出可能为 numpy.ndarray，序列化时转为 list。"""
        if value is None:
            return None
        if hasattr(value, "tolist"):
            return cast(list[float], value.tolist())
        return cast(list[float], value)

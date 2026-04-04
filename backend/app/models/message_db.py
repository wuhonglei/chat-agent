from datetime import datetime
from typing import Any

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlmodel import Field, SQLModel

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
    content_blocks: list[dict[str, Any]] | None = Field(
        default=None, sa_type=SQLJSON, description="Message content blocks"
    )
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=get_datetime_now,
        ),
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

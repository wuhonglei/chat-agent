"""会话级上下文：仅本会话的窗口外摘要"""

from datetime import datetime

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlmodel import Field, SQLModel

from app.utils.date import get_datetime_now


class ConversationContextDb(SQLModel, table=True):
    """会话级上下文：仅本会话的窗口外摘要"""

    __tablename__ = "conversation_contexts"

    conversation_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        description="对话 ID",
    )
    summary_before_window: str | None = Field(
        default=None,
        description="窗口外更早消息的摘要",
    )
    last_summarized_message_ids: list[str] | None = Field(
        default=None,
        sa_type=SQLJSON,
        description="上次已摘要的消息 id 列表（JSON 数组）",
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=get_datetime_now,
        ),
    )

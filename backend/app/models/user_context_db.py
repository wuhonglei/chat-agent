"""会话级上下文：仅本会话的窗口外摘要"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.utils.date import get_datetime_now


class UserContextDb(SQLModel, table=True):
    """会话级上下文：仅本会话的窗口外摘要"""

    __tablename__ = "user_contexts"

    user_id: str = Field(
        primary_key=True,
        max_length=36,
        description="用户 ID",
    )
    conversation_id: str = Field(
        primary_key=True,
        max_length=36,
        description="对话 ID",
    )
    summary_before_window: str | None = Field(
        default=None,
        description="窗口外更早消息的摘要",
    )
    recent_summary: str | None = Field(
        default=None,
        description="最近一次截断产生的摘要",
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True),
    )

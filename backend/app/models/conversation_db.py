from datetime import datetime

from sqlalchemy import Column, DateTime, Index, desc
from sqlmodel import Field, SQLModel

from app.schemas.conversation import CreatedBy
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class ConversationDb(SQLModel, table=True):
    """对话模型"""

    __tablename__ = "conversations"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index(
            "ix_conversations_user_active_last_msg",
            "user_id",
            "is_active",
            desc("last_message_created_at"),
            desc("id"),
        ),
        Index(
            "ix_conversations_user_active_pinned",
            "user_id",
            "is_active",
            desc("pinned_at"),
            desc("id"),
        ),
    )

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    title: str
    created_by: str = Field(
        default=CreatedBy.DEFAULT,
        description="标题创建方式",
    )
    user_id: str | None = Field(
        ...,
        index=True,
        max_length=36,
        foreign_key="users.id",
        description="关联用户",
    )
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_message_created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_message_updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    pinned_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="置顶时间，空表示未置顶",
    )
    is_active: bool = Field(default=True)

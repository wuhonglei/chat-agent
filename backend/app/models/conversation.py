from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field

from app.utils.date import get_datetime_now
from app.utils.common import gen_uuid
from app.schemas.conversation import CreatedBy


class ConversationDb(SQLModel, table=True):
    """对话模型"""
    __tablename__ = "conversations"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    title: str
    created_by: str = Field(
        default=CreatedBy.DEFAULT,
        description="标题创建方式",
    )
    user_id: Optional[str] = Field(
        ...,
        index=True,
        max_length=36,
        foreign_key="users.id",
        description="关联用户",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True)
    )
    last_message_created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True)
    )
    last_message_updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True)
    )
    is_active: bool = Field(default=True)

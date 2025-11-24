from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlmodel import SQLModel, Field

from app.utils.date import get_datetime_now
from app.utils.common import gen_uuid
from app.models.conversation import CreatedBy


class UserDb(SQLModel, table=True):
    """用户模型"""
    __tablename__ = "users"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    name: str = Field(..., description="User name")
    email: Optional[str] = Field(unique=True, index=True)
    avatar: Optional[str] = None
    phone: Optional[str] = Field(unique=True, index=True)
    sub: Optional[str] = Field(
        unique=True, index=True, description="User ID in the cloudbase")
    last_login_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True))
    last_logout_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True))
    last_login_type: Optional[str] = Field(
        default="sms", description="Last login type")
    role: str = Field(default="user")
    status: str = Field(default="active or inactive",
                        description="User status")
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True)
    )


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


class MessageDb(SQLModel, table=True):
    """消息模型"""
    __tablename__ = "messages"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    conversation_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            index=True
        ),
        description="关联对话",
    )
    role: str  # "user" | "assistant"
    content: str = Field(default="", description="Message content")
    created_at: datetime = Field(
        default_factory=get_datetime_now, index=True,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True)
    )
    reasoning: Optional[str] = Field(
        default=None, description="Reasoning content")
    tool_calls: Optional[list[dict]] = Field(
        default=None, sa_type=SQLJSON, description="Tool calls")
    message_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_type=SQLJSON)  # 元数据（模型调用、配置）
    status: str = Field(
        default="pending",
        description="消息落库状态，pending|done|failed"
    )
    reply_to: Optional[str] = Field(
        default=None,
        description="关联的用户消息 ID",
        max_length=36
    )

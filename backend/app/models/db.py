import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import DateTime, Enum as SQLEnum
from sqlmodel import SQLModel, Field

from app.utils.common import get_datetime_now
from app.models.llm import ToolCallMessage
from app.models.conversation import CreatedBy


def gen_uuid() -> str:
    """Generate a new UUID string"""
    return str(uuid.uuid4())


class User(SQLModel, table=True):
    """用户模型"""
    __tablename__ = "users"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    name: str
    email: str = Field(unique=True, index=True)
    avatar: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="user")
    status: str = Field(default="active")
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True)
    )


class Conversation(SQLModel, table=True):
    """对话模型"""
    __tablename__ = "conversations"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    title: str
    created_by: CreatedBy = Field(
        default=CreatedBy.DEFAULT,
        description="标题创建方式",
        sa_type=SQLEnum(CreatedBy)
    )
    user_id: Optional[str] = Field(
        default=None, index=True, max_length=36)  # 预留扩展
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True)
    )
    message_count: int = Field(default=0)
    is_active: bool = Field(default=True)


class Message(SQLModel, table=True):
    """消息模型"""
    __tablename__ = "messages"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    conversation_id: str = Field(index=True, max_length=36)
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime = Field(
        default_factory=get_datetime_now, index=True,
        sa_type=DateTime(timezone=True))
    reasoning: Optional[str] = None  # 推理内容
    tool_calls: Optional[list[ToolCallMessage]] = Field(
        default=None, sa_type=SQLJSON)  # 工具调用列表
    message_metadata:  dict[str, Any] = Field(
        default_factory=dict, sa_type=SQLJSON)  # 元数据（模型调用、配置）

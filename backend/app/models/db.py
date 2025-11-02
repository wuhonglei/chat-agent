import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import ConfigDict
from sqlalchemy import JSON as SQLJSON
from sqlmodel import SQLModel, Field


def get_current_time():
    return datetime.now(timezone.utc)


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
        default_factory=get_current_time)
    updated_at: datetime = Field(
        default_factory=get_current_time,
        sa_column_kwargs={"onupdate": get_current_time}
    )


class Conversation(SQLModel, table=True):
    """对话模型"""
    __tablename__ = "conversations"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    title: str
    user_id: Optional[str] = Field(
        default=None, index=True, max_length=36)  # 预留扩展
    created_at: datetime = Field(
        default_factory=get_current_time)
    updated_at: datetime = Field(
        default_factory=get_current_time,
        sa_column_kwargs={"onupdate": get_current_time}
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
    timestamp: datetime = Field(
        default_factory=get_current_time, index=True)
    reasoning: Optional[str] = None  # 推理内容（仅助手消息使用）
    tool_calls: Optional[dict[str, Any]] = Field(
        default=None, sa_type=SQLJSON)  # 工具调用列表（仅助手消息使用）
    message_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_type=SQLJSON)  # 元数据（模型调用、配置）

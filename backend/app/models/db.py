from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON as SQLJSON
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """用户模型"""
    __tablename__ = "users"

    id: str = Field(primary_key=True, index=True)
    name: str
    email: str = Field(unique=True, index=True)
    avatar: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="user")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class Conversation(SQLModel, table=True):
    """对话模型"""
    __tablename__ = "conversations"

    id: str = Field(primary_key=True, index=True)
    title: str
    user_id: Optional[str] = Field(default=None, index=True)  # 预留扩展
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )
    message_count: int = Field(default=0)
    is_active: bool = Field(default=True)


class Message(SQLModel, table=True):
    """消息模型"""
    __tablename__ = "messages"

    id: str = Field(primary_key=True, index=True)
    conversation_id: str = Field(index=True)
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    reasoning: Optional[str] = None  # 推理内容（仅助手消息使用）
    tool_calls: Optional[dict[str, Any]] = Field(
        default=None, sa_type=SQLJSON)  # 工具调用列表（仅助手消息使用）
    metadata: dict[str, Any] = Field(
        default_factory=dict, sa_type=SQLJSON)  # 元数据（模型调用、配置）

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, ForeignKey, String, Float
from sqlmodel import SQLModel, Field

from app.utils.date import get_datetime_now
from app.utils.common import gen_uuid


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
    component_tool_calls: Optional[list[dict]] = Field(
        default=None, sa_type=SQLJSON, description="Component tool calls")
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
    tool_calls_duration: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="工具调用耗时（秒）"
    )
    component_tool_calls_duration: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="组件工具调用耗时（秒）"
    )
    reasoning_duration: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="推理耗时（秒）"
    )
    content_duration: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="内容生成耗时（秒）"
    )
    total_duration: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="总耗时（秒）"
    )
    token_stats: Optional[dict] = Field(
        default=None,
        sa_type=SQLJSON,
        description="Token 使用统计信息，包含各个阶段（MCP 工具调用、组件工具调用、响应生成、标题生成）的 token 使用量"
    )

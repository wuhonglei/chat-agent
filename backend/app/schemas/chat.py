"""Chat models"""

from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.llm import ToolMessage
from app.utils.date import get_datetime_now


class MessageStatus(str, Enum):
    """Message status"""

    PENDING = "pending"  # 未完成(答案生成中)
    STOPPED = "stopped"  # 停止(答案生成停止)
    DONE = "done"  # 完成(答案生成完成)
    FAILED = "failed"  # 失败(答案生成失败)


class SourceConfig(BaseModel):
    """Source configuration model"""

    model_config = ConfigDict(extra="allow")


class ChatMessageItemReq(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role (user/assistant/tool)")
    content: str | None = Field(None, description="Message content")
    tool_call_id: str | None = Field(None, description="Tool call ID")
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None = Field(
        None, description="Tool calls"
    )


class ChatMessageItem(BaseModel):
    """Chat message response model"""

    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(default="", description="Message content")
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Message timestamp"
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_now, description="Message updated at"
    )
    reasoning: str | None = Field(default=None, description="Reasoning content")
    tool_calls: list[ToolMessage] | None = Field(default=None, description="Tool calls")
    message_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Message metadata"
    )
    status: str = Field(
        default="pending",
        description="Message persistence status (pending|done|failed)",
    )
    reply_to: str | None = Field(
        default=None,
        description="ID of the user message this assistant message replies to",
    )
    tool_calls_duration: float | None = Field(
        default=None, description="工具调用耗时（秒）"
    )
    reasoning_duration: float | None = Field(default=None, description="推理耗时（秒）")
    content_duration: float | None = Field(
        default=None, description="内容生成耗时（秒）"
    )
    total_duration: float | None = Field(default=None, description="总耗时（秒）")
    token_stats: dict[str, Any] | None = Field(
        default=None,
        description="Token 使用统计信息（MCP 工具调用、响应生成、标题生成等）",
    )

    model_config = ConfigDict(extra="ignore")


# ChatMessageItem 和 ToolMessage 的混合类型
ChatMessageItemWithToolCalls: TypeAlias = ChatMessageItem | ToolMessage


class ChatRequest(BaseModel):
    """Chat request model"""

    content: str = Field(..., description="User message")
    conversation_id: str = Field(..., description="Conversation ID")
    history_ids: list[str] = Field(default_factory=list, description="Chat history IDs")
    removed_message_ids: list[str] | None = Field(
        None, description="Message IDs to be removed"
    )
    source_config: SourceConfig = Field(
        default_factory=SourceConfig, description="Source configuration"
    )
    regenerate_title: bool | None = Field(
        False, description="Whether to regenerate title"
    )
    mcp_auto_mode: bool = Field(True, description="Whether to use mcp auto mode")
    think_mode: bool = Field(False, description="Whether to use think mode")


class ChatSource(BaseModel):
    """Chat source reference model"""

    content: str = Field(..., description="Source content snippet")
    title: str = Field(..., description="Source title")
    url: str | None = Field(None, description="Source URL")
    source: str = Field(
        ..., description="Source type (e.g., confluence, web, google_docs)"
    )
    score: float = Field(..., description="Relevance score")
    favicon: str | None = Field(None, description="Web search source favicon")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (last_modified_time, last_modifier_name, etc.)",
    )


class ChatResponse(BaseModel):
    """Chat response model"""

    message: str = Field(..., description="Assistant response")
    sources: list[ChatSource] = Field(
        default_factory=list, description="Source documents"
    )
    session_id: str = Field(..., description="Session ID")
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Response timestamp"
    )


class CollectedResponse(BaseModel):
    """Collected response model"""

    content: str = Field(default="", description="Collected content")
    reasoning: str = Field(default="", description="Collected reasoning")
    tool_calls: list[ToolMessage] = Field(
        default_factory=list, description="Collected tool calls"
    )
    tool_calls_duration: float | None = Field(
        default=None, description="MCP 工具调用耗时（秒）"
    )
    reasoning_duration: float | None = Field(default=None, description="推理耗时（秒）")
    content_duration: float | None = Field(
        default=None, description="内容生成耗时（秒）"
    )
    total_duration: float | None = Field(default=None, description="总耗时（秒）")
    token_stats: dict[str, Any] | None = Field(
        default=None,
        description="Token 使用统计信息（MCP 工具调用、响应生成、标题生成等）",
    )

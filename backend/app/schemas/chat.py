"""Chat models"""

from datetime import datetime
from typing import Any, Optional, Literal
from enum import Enum

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, Field, ConfigDict

from app.utils.date import get_datetime_now


class MessageStatus(str, Enum):
    """Message status"""
    PENDING = "pending"  # 未完成(答案生成中)
    STOPPED = "stopped"  # 停止(答案生成停止)
    DONE = "done"  # 完成(答案生成完成)
    FAILED = "failed"  # 失败(答案生成失败)


class SourceConfig(BaseModel):
    """Source configuration model"""
    model_config = ConfigDict(
        extra='allow'
    )


class ComponentToolWhen(BaseModel):
    """Component tool when condition model"""
    mcp_tool_names: Optional[list[str]] = Field(
        None, description="当 mcp 工具名称匹配时，后端才会组装对应的组件"
    )
    mcp_tool_call_content: Optional[list[str]] = Field(
        None, description="当 mcp 工具调用内容匹配时，后端才会组装对应的组件"
    )
    user_message: Optional[str] = Field(
        None, description="当用户消息内容匹配时，后端才会组装对应的组件"
    )


class ComponentToolConfig(BaseModel):
    """Component tool configuration model"""
    name: str = Field(..., description="Component tool name, e.g. 'weather'")
    when_condition: Literal["and", "or"] = Field(
        "and", description="Condition logic: 'and' or 'or'"
    )
    when: ComponentToolWhen = Field(
        default_factory=ComponentToolWhen, description="When condition configuration"
    )


class ChatMessageItemReq(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role (user/assistant/tool)")
    content: Optional[str] = Field(None, description="Message content")
    tool_call_id: Optional[str] = Field(
        None, description="Tool call ID")
    tool_calls: Optional[list[ChatCompletionMessageFunctionToolCall]] = Field(
        None, description="Tool calls")


class ChatMessageItem(BaseModel):
    """Chat message response model"""
    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    conversation_id: str = Field(..., description="Conversation ID")
    reasoning: Optional[str] = Field(None, description="Reasoning content")
    tool_calls: Optional[list[dict]] = Field(
        None, description="Tool calls")
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Message timestamp")
    message_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Message metadata")
    status: str = Field(
        default="pending",
        description="Message persistence status (pending|done|failed)"
    )
    reply_to: Optional[str] = Field(
        default=None,
        description="ID of the user message this assistant message replies to"
    )
    tool_calls_duration: Optional[float] = Field(
        default=None,
        description="工具调用耗时（秒）"
    )
    reasoning_duration: Optional[float] = Field(
        default=None,
        description="推理耗时（秒）"
    )
    content_duration: Optional[float] = Field(
        default=None,
        description="内容生成耗时（秒）"
    )
    total_duration: Optional[float] = Field(
        default=None,
        description="总耗时（秒）"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Message created at")
    updated_at: datetime = Field(
        default_factory=get_datetime_now, description="Message updated at")

    model_config = ConfigDict(
        extra='allow'
    )


class ChatRequest(BaseModel):
    """Chat request model"""

    content: str = Field(..., description="User message")
    conversation_id: str = Field(
        ..., description="Conversation ID")
    history_ids: list[str] = Field(
        default_factory=list, description="Chat history IDs")
    removed_message_ids: Optional[list[str]] = Field(
        None, description="Message IDs to be removed")
    source_config: SourceConfig = Field(
        default_factory=SourceConfig, description="Source configuration"
    )
    regenerate_title: Optional[bool] = Field(
        False, description="Whether to regenerate title")
    mcp_auto_mode: bool = Field(
        True, description="Whether to use mcp auto mode")
    think_mode: bool = Field(False, description="Whether to use think mode")
    component_tools_for_backend: list[ComponentToolConfig] = Field(
        default_factory=list, description="Component tools for backend")


class ChatSource(BaseModel):
    """Chat source reference model"""

    content: str = Field(..., description="Source content snippet")
    title: str = Field(..., description="Source title")
    url: Optional[str] = Field(None, description="Source URL")
    source: str = Field(...,
                        description="Source type (e.g., confluence, web, google_docs)")
    score: float = Field(..., description="Relevance score")
    favicon: Optional[str] = Field(
        None, description="Web search source favicon")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (last_modified_time, last_modifier_name, etc.)"
    )


class ChatResponse(BaseModel):
    """Chat response model"""

    message: str = Field(..., description="Assistant response")
    sources: list[ChatSource] = Field(
        default_factory=list, description="Source documents")
    session_id: str = Field(..., description="Session ID")
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Response timestamp")


class CollectedResponse(BaseModel):
    """Collected response model"""
    content: str = Field(default="", description="Collected content")
    reasoning: str = Field(default="", description="Collected reasoning")
    tool_calls: list[dict] = Field(
        default_factory=list, description="Collected tool calls")
    component_tool_calls: list[dict] = Field(
        default_factory=list, description="Collected component tool calls")
    tool_calls_duration: Optional[float] = Field(
        default=None,
        description="MCP 工具调用耗时（秒）"
    )
    component_tool_calls_duration: Optional[float] = Field(
        default=None,
        description="组件工具调用耗时（秒），不包含 MCP 工具调用耗时"
    )
    reasoning_duration: Optional[float] = Field(
        default=None,
        description="推理耗时（秒）"
    )
    content_duration: Optional[float] = Field(
        default=None,
        description="内容生成耗时（秒）"
    )
    total_duration: Optional[float] = Field(
        default=None,
        description="总耗时（秒）"
    )

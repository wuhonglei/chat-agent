from typing import Any, Literal, TypeAlias

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, Field


class ToolUseMessage(BaseModel):
    role: Literal["assistant"]
    content: str | None
    reasoning_content: str | None
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None


class ToolResultMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    is_error: bool
    content: str
    structured_content_for_display: list[dict[str, Any]] | None = Field(
        default=None,
        description="前端展示使用的轻量结构化结果；存在时 SSE 可省略 content",
    )
    summary: str | None = Field(
        default=None, description="单个工具结果摘要, 如果为空则默认使用 content 内容值"
    )


ToolMessage: TypeAlias = ToolUseMessage | ToolResultMessage

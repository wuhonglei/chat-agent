from typing import Literal, TypeAlias

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
    summary: str | None = Field(
        default=None, description="单个工具结果摘要, 如果为空则默认使用 content 内容值"
    )
    duration: float
    relevance_applied: bool | None = Field(
        default=None, description="是否应用相关性过滤"
    )
    content_token_count: int | None = Field(default=None, description="内容tokens数")
    original_token_count: int | None = Field(
        default=None, description="原始内容tokens数"
    )
    relevant_token_count: int | None = Field(
        default=None, description="相关内容tokens数"
    )
    threshold_token_count: int | None = Field(
        default=None, description="压缩阈值tokens数"
    )


ToolMessage: TypeAlias = ToolUseMessage | ToolResultMessage

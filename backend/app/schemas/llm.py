from typing import Literal, TypeAlias

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, Field


class AssistantToolCallMessage(BaseModel):
    role: Literal["assistant"]
    content: str | None
    content_token_count: int | None = Field(
        default=None, description="Content token count"
    )
    reasoning_content: str | None
    reasoning_token_count: int | None = Field(
        default=None, description="Reasoning token count"
    )
    tool_call_token_count: int | None = Field(
        default=None, description="Tool call token count"
    )
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None


class ToolCallResultMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    is_error: bool
    content: str
    duration: float
    relevance_applied: bool | None = Field(
        default=None, description="Whether relevance filtering applied"
    )
    content_token_count: int | None = Field(
        default=None, description="Content token count"
    )
    original_token_count: int | None = Field(
        default=None, description="Original content token count"
    )
    relevant_token_count: int | None = Field(
        default=None, description="Relevant content token count"
    )
    threshold_token_count: int | None = Field(
        default=None, description="Compression threshold token count"
    )


ToolCallMessage: TypeAlias = AssistantToolCallMessage | ToolCallResultMessage

from typing import Literal, TypeAlias

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, Field


class AssistantToolCallMessage(BaseModel):
    role: Literal["assistant"]
    content: str | None
    reasoning_content: str | None
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None


class ToolCallResultMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    is_error: bool
    content: str
    duration: float
    token_count: int | None = Field(default=None, description="Content token count")
    reference_id: str | None = Field(default=None, description="Reference ID")
    relevance_applied: bool | None = Field(
        default=None, description="Whether relevance filtering applied"
    )
    summary_applied: bool | None = Field(
        default=None, description="Whether summarization applied"
    )
    original_tokens: int | None = Field(
        default=None, description="Original content token count"
    )
    relevant_tokens: int | None = Field(
        default=None, description="Relevant content token count"
    )
    summary_tokens: int | None = Field(
        default=None, description="Summary content token count"
    )
    threshold_tokens: int | None = Field(
        default=None, description="Compression threshold token count"
    )


ToolCallMessage: TypeAlias = AssistantToolCallMessage | ToolCallResultMessage

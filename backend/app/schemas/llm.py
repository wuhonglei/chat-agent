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


ToolCallMessage: TypeAlias = AssistantToolCallMessage | ToolCallResultMessage

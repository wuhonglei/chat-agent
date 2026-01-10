from typing import Literal, Optional, TypeAlias
from pydantic import BaseModel
from openai.types.chat import ChatCompletionMessageFunctionToolCall


class AssistantToolCallMessage(BaseModel):
    role: Literal["assistant"]
    content: Optional[str]
    reasoning_content: Optional[str]
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None


class ToolCallResultMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    is_error: bool
    content: str
    duration: float
    token_count: Optional[int]  # content token 计数


ToolCallMessage: TypeAlias = AssistantToolCallMessage | ToolCallResultMessage

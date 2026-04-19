"""Chat models"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal, TypeAlias, cast

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class MessageStatus(str, Enum):
    """Message status"""

    PENDING = "pending"  # 未完成(答案生成中)
    STOPPED = "stopped"  # 停止(答案生成停止)
    DONE = "done"  # 完成(答案生成完成)
    FAILED = "failed"  # 失败(答案生成失败)


class MessageFeedbackValue(str, Enum):
    """Message feedback value"""

    DEFAULT = "default"
    LIKE = "like"
    DISLIKE = "dislike"


class MessageFeedback(BaseModel):
    """Message feedback payload"""

    value: MessageFeedbackValue = Field(
        default=MessageFeedbackValue.DEFAULT, description="Feedback value"
    )
    updated_at: datetime | None = Field(
        default=None, description="Feedback updated timestamp"
    )


class SourceConfig(BaseModel):
    """Source configuration model"""

    model_config = ConfigDict(extra="allow")


class ChatMessageRequestItem(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role (user/assistant/tool)")
    content: str | None = Field(None, description="Message content")
    tool_call_id: str | None = Field(None, description="Tool call ID")
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None = Field(
        None, description="Tool calls"
    )


class ChatMessage(BaseModel):
    """Chat message response model"""

    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    role: str = Field(..., description="Message role (user/assistant)")
    content_blocks: list["ContentBlock"] = Field(
        default_factory=list, description="Message content blocks"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_now, description="Message timestamp"
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_now, description="Message updated at"
    )
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
    feedback: MessageFeedback | None = Field(
        default=None, description="Message feedback"
    )

    model_config = ConfigDict(extra="ignore")


# ChatMessage 和 ToolMessage 的混合类型
ChatMessageWithToolCalls: TypeAlias = ChatMessage | ToolMessage


class ChatRequest(BaseModel):
    """Chat request model"""

    content_blocks: list["ContentBlock"] = Field(
        ..., description="User message content blocks"
    )
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

    @field_validator("content_blocks", mode="before")
    @classmethod
    def reject_client_kb_context_blocks(cls, value: Any) -> Any:
        if not value:
            return value
        for block in value:
            if isinstance(block, dict) and block.get("type") == "kb_context":
                raise ValueError("kb_context block is server-side only")
            if isinstance(block, KbContextBlock):
                raise ValueError("kb_context block is server-side only")
        return value


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


class AssistantResponse(BaseModel):
    """Collected response model"""

    content: str = Field(default="", description="Collected content")
    reasoning: str = Field(default="", description="Collected reasoning")
    content_blocks: list["ContentBlock"] = Field(
        default_factory=list, description="Collected content blocks"
    )


class TextBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["text"] = "text"
    text: str = Field(default="", description="Text content")


class ThinkingBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["thinking"] = "thinking"
    text: str = Field(default="", description="Thinking content")


class ToolUseBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["tool_use"] = "tool_use"
    tool_call_id: str | None = Field(default=None, description="Tool call ID")
    name: str | None = Field(default=None, description="Tool name")
    arguments_text: str = Field(default="", description="Tool arguments text")
    arguments_json: dict[str, Any] | None = Field(
        default=None, description="Parsed tool arguments"
    )


class ToolResultBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_use_id: str = Field(..., description="Referenced tool_use block ID")
    is_error: bool = Field(default=False, description="Tool result error status")
    content: str = Field(default="", description="Tool result content")
    structured_content_for_display: list[dict[str, Any]] | None = Field(
        default=None, description="供前端展示的轻量结构化工具结果"
    )
    summary: str | None = Field(default=None, description="Tool result summary")


class ImageBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["image"] = "image"
    url: str = Field(..., description="Preview URL path (e.g. /api/file/preview/...)")
    name: str = Field(
        default="",
        max_length=240,
        description="展示用文件名（已安全化）；历史数据可能为空",
    )
    size: int = Field(
        ...,
        ge=0,
        description="落盘文件字节数（经缩放/重编码等处理后的实际大小）",
    )
    mime: str = Field(..., description="MIME type e.g. image/jpeg")


class MarkdownBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["markdown"] = "markdown"
    url: str = Field(..., description="Preview URL path (e.g. /api/file/preview/...)")
    name: str = Field(
        default="",
        max_length=240,
        description="展示用文件名（已安全化）；历史数据可能为空",
    )
    size: int = Field(
        ...,
        ge=0,
        description="落盘文件字节数",
    )
    mime: Literal["text/markdown"] = Field(
        default="text/markdown",
        description="MIME type for Markdown",
    )


class PdfBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    type: Literal["pdf"] = "pdf"
    url: str = Field(..., description="Preview URL path (e.g. /api/file/preview/...)")
    name: str = Field(
        default="",
        max_length=240,
        description="展示用文件名（已安全化）；历史数据可能为空",
    )
    size: int = Field(
        ...,
        ge=0,
        description="落盘文件字节数",
    )
    mime: Literal["application/pdf"] = Field(
        default="application/pdf",
        description="MIME type for PDF",
    )
    markdown: MarkdownBlock | None = Field(  # pyright: ignore[reportUndefinedVariable]
        default=None, description="Markdown block"
    )


class KbContextBlock(BaseModel):
    id: str = Field(..., description="附件 file_id")
    type: Literal["kb_context"] = "kb_context"
    name: str = Field(default="", description="附件文件名")
    created_at: str | None = Field(default=None, description="附件创建相对时间")
    content: str = Field(default="", description="Knowledge base context content")


AttachmentBlock: TypeAlias = ImageBlock | MarkdownBlock | PdfBlock

ContentBlock: TypeAlias = (
    TextBlock
    | ThinkingBlock
    | ToolUseBlock
    | ToolResultBlock
    | ImageBlock
    | PdfBlock
    | MarkdownBlock
    | KbContextBlock
)
_CONTENT_BLOCKS_ADAPTER = TypeAdapter(list[ContentBlock])


def normalize_content_blocks(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
) -> list[ContentBlock]:
    if not content_blocks:
        return []
    return _CONTENT_BLOCKS_ADAPTER.validate_python(content_blocks)


def extract_user_text(content_blocks: list[ContentBlock]) -> str:
    return "".join(
        block.text for block in content_blocks if isinstance(block, TextBlock)
    ).strip()


def collect_text_from_blocks(
    content_blocks: list[ContentBlock], only_last: bool = False
) -> str:
    text_blocks = [
        block.text for block in content_blocks if isinstance(block, TextBlock)
    ]
    if only_last:
        return text_blocks[-1] if text_blocks else ""
    return "".join(text_blocks)


def collect_reasoning_from_blocks(
    content_blocks: list[ContentBlock], only_last: bool = False
) -> str:
    thinking_blocks = [
        block.text for block in content_blocks if isinstance(block, ThinkingBlock)
    ]
    if only_last:
        return thinking_blocks[-1] if thinking_blocks else ""
    return "".join(thinking_blocks)


def collect_content_from_block_payloads(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    only_last: bool = False,
) -> str:
    return collect_text_from_blocks(
        normalize_content_blocks(content_blocks), only_last=only_last
    )


def collect_reasoning_from_block_payloads(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    only_last: bool = False,
) -> str:
    return collect_reasoning_from_blocks(
        normalize_content_blocks(content_blocks), only_last=only_last
    )


def dump_content_block_payloads(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    omit_tool_result_content_and_summary_when_structured: bool = False,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for block in normalize_content_blocks(content_blocks):
        payload = block.model_dump(mode="json")
        if (
            omit_tool_result_content_and_summary_when_structured
            and isinstance(block, ToolResultBlock)
            and block.structured_content_for_display is not None
        ):
            payload.pop("content", None)
            payload.pop("summary", None)
        payloads.append(payload)
    return payloads


def replace_text_content_blocks(
    content_blocks: list[ContentBlock] | list[dict[str, Any]] | None,
    text: str,
) -> list[ContentBlock]:
    normalized_blocks = normalize_content_blocks(content_blocks)
    non_text_blocks = [
        block for block in normalized_blocks if not isinstance(block, TextBlock)
    ]
    if not text:
        return cast(list[ContentBlock], non_text_blocks)
    return [TextBlock(id=gen_uuid(), text=text), *non_text_blocks]


def tool_messages_from_content_blocks(
    content_blocks: list[ContentBlock],
) -> list[ToolMessage]:
    tool_messages: list[ToolMessage] = []

    for block in content_blocks:
        if isinstance(block, ToolUseBlock):
            if not block.tool_call_id:
                continue
            arguments_text = block.arguments_text or "{}"
            try:
                json.loads(arguments_text)
            except Exception:
                arguments_text = "{}"
            tool_call = ChatCompletionMessageFunctionToolCall.model_validate(
                {
                    "id": block.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": block.name or "",
                        "arguments": arguments_text,
                    },
                }
            )
            tool_message = ToolUseMessage(
                role="assistant",
                content="",
                reasoning_content="",
                tool_calls=[tool_call],
            )
            tool_messages.append(tool_message)
            continue

        if isinstance(block, ToolResultBlock):
            tool_messages.append(
                ToolResultMessage(
                    role="tool",
                    tool_call_id=block.tool_call_id,
                    is_error=block.is_error,
                    content=block.content,
                    structured_content_for_display=block.structured_content_for_display,
                    summary=block.summary,
                )
            )
    return tool_messages


def count_tool_use_blocks(content_blocks: list[ContentBlock]) -> int:
    return sum(1 for block in content_blocks if isinstance(block, ToolUseBlock))


ChatMessage.model_rebuild()
ChatRequest.model_rebuild()
AssistantResponse.model_rebuild()

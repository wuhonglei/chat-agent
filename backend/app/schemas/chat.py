"""Chat models"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Self, TypeAlias, cast

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.mcp.tool_naming import llm_tool_name
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now
from app.utils.file import format_human_size


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
    reasons: list[str] = Field(
        default_factory=list, description="Selected feedback reason tags"
    )
    comment: str | None = Field(
        default=None, description="Optional free-text feedback comment"
    )


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
    regenerate_title: bool | None = Field(
        False, description="Whether to regenerate title"
    )
    agent_mode: int = Field(0, description="Agent mode: 0=disabled, 1=enabled")
    think_mode: bool = Field(False, description="Whether to use think mode")
    model_id: str = Field(
        default="",
        description="模型引用（provider/model_name，如 dashscope/kimi-k2.6）；"
        "为空或无法解析时回退 text_generation 场景默认模型",
    )
    client_turn_id: str | None = Field(
        default=None,
        description="Client-generated idempotency key for one user turn",
    )
    mentioned_blocks: list["AttachmentBlock"] = Field(
        default_factory=list,
        description="通过 @ 引用的附件块（不并入 content_blocks）",
    )

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


class StreamResumeRequest(BaseModel):
    """SSE resume request model"""

    assistant_message_id: str = Field(..., description="Assistant message ID")


class StreamStopRequest(BaseModel):
    """SSE stop request model"""

    assistant_message_id: str = Field(..., description="Assistant message ID")


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
    name: str | None = Field(default=None, description="LLM-visible tool name")
    server_name: str | None = Field(default=None, description="MCP server config key")
    mcp_tool_name: str | None = Field(
        default=None, description="Original MCP tool name (bare)"
    )
    arguments_text: str = Field(default="", description="Tool arguments text")
    arguments_json: dict[str, Any] | None = Field(
        default=None, description="Parsed tool arguments"
    )

    @model_validator(mode="after")
    def validate_tool_naming_fields(self) -> Self:
        if not self.name:
            return self
        if not self.server_name or not self.mcp_tool_name:
            raise ValueError(
                f"ToolUseBlock {self.id!r}: name 存在时必须同时提供 "
                "server_name 与 mcp_tool_name"
            )
        expected = llm_tool_name(self.server_name, self.mcp_tool_name)
        if self.name != expected:
            raise ValueError(
                f"ToolUseBlock {self.id!r}: name 应为 {expected!r}，"
                f"实际为 {self.name!r}"
            )
        return self


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


class AttachmentBaseBlock(BaseModel):
    id: str = Field(..., description="Block ID")
    url: str = Field(..., description="Preview URL path (e.g. /api/file/preview/...)")
    storage_key: str | None = Field(
        default=None,
        description="Conversation-scoped storage key, e.g. {conversation_id}/{display_name}",
    )
    storage_version: int | None = Field(
        default=None, description="Storage schema version"
    )
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
    token_size: int | None = Field(
        default=None,
        ge=0,
        description="附件文本 token 数（上传时计算；历史数据可能缺省）",
    )
    lines_count: int | None = Field(
        default=None,
        ge=0,
        description="文本内容行数（文本类型上传时计算；历史数据可能缺省）",
    )


class ImageBlock(AttachmentBaseBlock):
    type: Literal["image"] = "image"
    mime: str = Field(..., description="MIME type e.g. image/jpeg")


class MarkdownBlock(AttachmentBaseBlock):
    type: Literal["markdown"] = "markdown"
    derived_from_id: str | None = Field(
        default=None, description="Source attachment content ID for derived files"
    )
    derived_kind: str | None = Field(
        default=None, description="Derived file relationship kind"
    )
    mime: Literal["text/markdown"] = Field(
        default="text/markdown",
        description="MIME type for Markdown",
    )


class PdfBlock(AttachmentBaseBlock):
    type: Literal["pdf"] = "pdf"
    mime: Literal["application/pdf"] = Field(
        default="application/pdf",
        description="MIME type for PDF",
    )
    markdown: MarkdownBlock | None = Field(  # pyright: ignore[reportUndefinedVariable]
        default=None, description="Markdown block"
    )


class ExcelBlock(AttachmentBaseBlock):
    type: Literal["excel"] = "excel"
    mime: Literal[
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ] = Field(
        default="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description="MIME type for Excel (.xlsx)",
    )
    markdown: MarkdownBlock | None = Field(default=None, description="Markdown block")


class DocxBlock(AttachmentBaseBlock):
    type: Literal["docx"] = "docx"
    mime: Literal[
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ] = Field(
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        description="MIME type for Word (.docx)",
    )
    markdown: MarkdownBlock | None = Field(default=None, description="Markdown block")


class PptxBlock(AttachmentBaseBlock):
    type: Literal["pptx"] = "pptx"
    mime: Literal[
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ] = Field(
        default="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        description="MIME type for PowerPoint (.pptx)",
    )
    markdown: MarkdownBlock | None = Field(default=None, description="Markdown block")


class TextFileBlock(AttachmentBaseBlock):
    type: Literal["text_file"] = "text_file"
    mime: str = Field(
        default="text/plain",
        description="MIME type for plain text / code files (e.g. text/csv, text/plain)",
    )


class KbContextBlock(BaseModel):
    id: str = Field(..., description="附件 content_id")
    type: Literal["kb_context"] = "kb_context"
    name: str = Field(default="", description="附件文件名")
    created_at: str | None = Field(default=None, description="附件创建相对时间")
    content: str = Field(default="", description="Knowledge base context content")


class AttachmentFileInfo(BaseModel):
    """上传文件元信息，供模型用文件工具按需读取。"""

    name: str = Field(..., description="展示用文件名")
    type: str = Field(
        ...,
        description='文件类型："pdf" | "excel" | "docx" | "pptx" | "markdown" | "image" | "text_file"',
    )
    size: int = Field(default=0, ge=0, description="落盘文件字节数")
    token_size: int | None = Field(
        default=None,
        ge=0,
        description="附件文本 token 数（文本类型有值；历史数据可能缺省）",
    )
    lines_count: int | None = Field(
        default=None,
        ge=0,
        description="文本内容行数（文本类型有值；历史数据可能缺省）",
    )
    virtual_path: str = Field(
        ..., description="文件虚拟路径，如 /mnt/user-data/uploads/{name}"
    )

    @property
    def human_size(self) -> str:
        """将字节数格式化为可读形式（B / KB / MB / GB）。"""
        return format_human_size(self.size)


class AttachmentUploadInfo(AttachmentFileInfo):
    """agent_mode 下注入用户消息的上传文件清单条目。"""

    markdown: AttachmentFileInfo | None = Field(
        default=None,
        description="PDF/Excel/Word/PowerPoint 派生的可读 Markdown 文件；其它类型为 None",
    )
    is_current_turn: bool = Field(default=False, description="是否为本轮上传")


AttachmentBlock: TypeAlias = (
    ImageBlock
    | MarkdownBlock
    | PdfBlock
    | ExcelBlock
    | DocxBlock
    | PptxBlock
    | TextFileBlock
)

ContentBlock: TypeAlias = (
    TextBlock
    | ThinkingBlock
    | ToolUseBlock
    | ToolResultBlock
    | ImageBlock
    | PdfBlock
    | ExcelBlock
    | DocxBlock
    | PptxBlock
    | MarkdownBlock
    | TextFileBlock
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

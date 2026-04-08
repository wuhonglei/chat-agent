"""Chat message and SSE protocol helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from toolz import get

from app.schemas.chat import (
    ChatMessageWithToolCalls,
    collect_content_from_block_payloads,
    collect_reasoning_from_block_payloads,
)
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.utils.common import normalize_to_dict
from app.utils.model import format_sse_message

EVENT_ACK = "ack"
EVENT_CONTENT_BLOCK = "content_block"
EVENT_DONE = "done"
EVENT_ERROR = "error"
EVENT_REFRESH_CONVERSATION = "refresh_conversation"
EVENT_TITLE = "title"


def format_tool_use_message(
    message: ToolUseMessage | dict[str, Any],
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    message = normalize_to_dict(message)
    return {
        "role": get("role", message),
        "content": get("content", message, None),
        "reasoning_content": None
        if clear_reasoning_content
        else get("reasoning_content", message, None),
        "tool_calls": get("tool_calls", message),
    }


def format_tool_result_message(
    message: ToolResultMessage | dict[str, Any],
) -> dict[str, Any]:
    message = normalize_to_dict(message)
    return {
        "role": get("role", message),
        "tool_call_id": get("tool_call_id", message),
        "content": get("content", message, ""),
    }


def format_tool_call_message_for_llm(
    message: ToolMessage | dict[str, Any],
    clear_reasoning_content: bool = False,
) -> dict[str, Any]:
    message = normalize_to_dict(message)
    if get("role", message) == "assistant":
        return format_tool_use_message(message, clear_reasoning_content)
    return format_tool_result_message(message)


def format_tool_call_messages_for_llm(
    messages: Sequence[ToolMessage | dict[str, Any]],
    clear_reasoning_content: bool = False,
) -> list[dict[str, Any]]:
    return [
        format_tool_call_message_for_llm(message, clear_reasoning_content)
        for message in messages
    ]


def format_chat_message_for_llm(
    message: ChatMessageWithToolCalls,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    if isinstance(message, ToolMessage):
        return format_tool_call_message_for_llm(message)

    message_dict = normalize_to_dict(message)
    content_blocks = get("content_blocks", message_dict, None)
    if content_blocks is not None:
        # TODO: 这里的 content 计算的是该消息 content_blocks 内的所有 TextBlock 的 text 字段拼接起来的字符串, 而不是最后一条 TextBlock 的 text 字段
        content = collect_content_from_block_payloads(content_blocks)
        # TODO: 这里的 reasoning 计算的是该消息 content_blocks 内的所有 ThinkingBlock 的 text 字段拼接起来的字符串, 而不是最后一条 ThinkingBlock 的 text 字段
        reasoning = collect_reasoning_from_block_payloads(content_blocks) or None
    else:
        content = get("content", message_dict, "")
        reasoning = get("reasoning", message_dict, None)
    payload: dict[str, Any] = {
        "role": get("role", message_dict),
        "content": content,
        "reasoning": reasoning,
    }
    if clear_reasoning_content:
        del payload["reasoning"]
    return payload


def build_content_block_event(data: dict[str, Any]) -> str:
    return format_sse_message(EVENT_CONTENT_BLOCK, data)


def build_content_block_done_event() -> str:
    return build_content_block_event({"op": "done"})


def build_ack_event(data: Any) -> str:
    return format_sse_message(EVENT_ACK, data)


def build_title_event(data: dict[str, Any]) -> str:
    return format_sse_message(EVENT_TITLE, data)


def build_done_event(data: dict[str, Any]) -> str:
    return format_sse_message(EVENT_DONE, data)


def build_error_event(data: dict[str, Any]) -> str:
    return format_sse_message(EVENT_ERROR, data)


def build_refresh_conversation_event(data: Any) -> str:
    return format_sse_message(EVENT_REFRESH_CONVERSATION, data)

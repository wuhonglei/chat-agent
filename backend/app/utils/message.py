"""消息处理工具函数"""

from typing import Any

from toolz import dissoc

from app.protocols import chat_messages as chat_protocol
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage

# Provider chat.completions 允许的消息字段（不含内部 source 等元数据）
_PROVIDER_MESSAGE_KEYS = (
    "role",
    "content",
    "name",
    "tool_call_id",
    "tool_calls",
    "reasoning_content",
)


def create_user_message(content: str, *, source: dict[str, Any]) -> dict[str, Any]:
    """创建带 source 标记的 user 消息（DeepSeek Harness 风格）。

    ``source`` 仅供内部组装 / 调试；发给 provider 前须经
    :func:`project_messages_for_provider` 剥离。
    """
    return {"role": "user", "content": content, "source": source}


def project_messages_for_provider(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """投影为 provider 允许的字段，去掉 ``source`` 等内部元数据。"""
    projected: list[dict[str, Any]] = []
    for message in messages:
        projected.append(
            {key: message[key] for key in _PROVIDER_MESSAGE_KEYS if key in message}
        )
    return projected


def build_trailing_hint_user_message(
    *,
    iteration_hints: str | None = None,
    guardrail_warns: list[str] | None = None,
    extra_notice: str | None = None,
    extra_plugin: str = "iteration_checkpoint",
) -> dict[str, Any] | None:
    """合并 iteration hints、熔断 WARN、可选 extra notice 为至多一条尾部 user。

    - 仅一种：``form=notice``，``plugin`` 为对应名
    - 多种并存：一条消息，``form=snapshot``，按 hints → warns → extra 顺序
    """
    hints_text = (iteration_hints or "").strip() or None
    warn_parts = [w.strip() for w in (guardrail_warns or []) if w and w.strip()]
    warns_text = "\n\n".join(warn_parts) if warn_parts else None
    extra_text = (extra_notice or "").strip() or None

    sections: list[dict[str, str]] = []
    content_parts: list[str] = []
    if hints_text:
        sections.append({"name": "iteration_hints", "text": hints_text})
        content_parts.append(hints_text)
    if warns_text:
        sections.append({"name": "tool_guardrail", "text": warns_text})
        content_parts.append(warns_text)
    if extra_text:
        sections.append({"name": extra_plugin, "text": extra_text})
        content_parts.append(extra_text)

    if not content_parts:
        return None

    if len(sections) == 1:
        only = sections[0]
        name = only["name"]
        text = only["text"]
        if name == "iteration_hints":
            content = f"注意:\n{text}"
            plugin = "iteration_hints"
        elif name == "tool_guardrail":
            content = text
            plugin = "tool_guardrail"
        else:
            content = text
            plugin = name
        return create_user_message(
            content,
            source={
                "kind": "plugin",
                "plugin": plugin,
                "form": "notice",
            },
        )

    # 多种并存：hints 前缀「注意:」，其余原样
    merged: list[str] = []
    if hints_text:
        merged.append(f"注意:\n{hints_text}")
    if warns_text:
        merged.append(warns_text)
    if extra_text:
        merged.append(extra_text)
    return create_user_message(
        "\n\n".join(merged),
        source={
            "kind": "plugin",
            "plugin": "agent_hints",
            "form": "snapshot",
            "sections": sections,
        },
    )


def clear_reasoning_content_from_history(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """清除历史消息中的 reasoning_content 字段。"""
    return [dissoc(d, "reasoning_content") for d in history]


def format_tool_use_message(
    message: ToolUseMessage | dict[str, Any],
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    return chat_protocol.format_tool_use_message(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_tool_result_message(
    message: ToolResultMessage | dict[str, Any],
) -> dict[str, Any]:
    return chat_protocol.format_tool_result_message(message)


def format_tool_call_message_for_llm(
    message: ToolMessage | dict[str, Any],
    clear_reasoning_content: bool = False,
) -> dict[str, Any]:
    return chat_protocol.format_tool_call_message_for_llm(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_tool_call_messages_for_llm(
    messages: list[ToolMessage | dict[str, Any]],
    clear_reasoning_content: bool = False,
) -> list[dict[str, Any]]:
    return chat_protocol.format_tool_call_messages_for_llm(
        messages,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_chat_message_for_llm(
    message: Any,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    return chat_protocol.format_chat_message_for_llm(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def get_assistant_tool_call_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolUseMessage]:
    """获取 assistant 工具调用消息。"""
    return [
        message for message in tool_call_messages if isinstance(message, ToolUseMessage)
    ]


def get_tool_call_result_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolResultMessage]:
    """获取 tool 工具调用消息。"""
    return [
        message
        for message in tool_call_messages
        if isinstance(message, ToolResultMessage)
    ]


def find_last_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """查找最后一个用户消息。"""
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def update_last_user_message(messages: list[dict[str, Any]], new_content: str) -> None:
    """更新最后一个用户消息。"""
    last_user_message = find_last_user_message(messages)
    if not last_user_message:
        return

    current_content = last_user_message.get("content")
    if isinstance(current_content, list):
        for part in current_content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                part["text"] = new_content
                return
        # 没有 text 分段时补一个，保留已有图片分段
        current_content.insert(0, {"type": "text", "text": new_content})
        return

    last_user_message["content"] = new_content

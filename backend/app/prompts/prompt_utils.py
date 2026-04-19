"""提示词工具函数模块"""

from typing import Any

from app.mcp.mcp_client import mcp_config_for_fe
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_chat_session_template,
    system_prompt_for_title_template,
    user_context_system_fragment_template,
)
from app.prompts.user_prompt import (
    WINDOW_OUT_SUMMARY_MERGE_PROMPT,
    disabled_tools_message_template,
    gentle_tips_in_web_search_template,
    tool_call_sufficient_info_template,
    user_message_for_default_template,
    user_message_for_no_tool_call_template,
    user_message_for_reach_tool_call_limit_template,
    user_message_for_tool_call_template,
)
from app.schemas.chat import ContentBlock
from app.utils.date import get_current_datetime_str


def get_default_system_prompt() -> str:
    """Get default system prompt with current time information"""
    return default_system_prompt_template.render()


def get_merged_system_prompt_for_chat_session(
    user_memories: list[str] | None = None,
    window_out_summary: str | None = None,
) -> str:
    """Get system prompt for final response generation.
    当传入 user_memories / window_out_summary 时注入对应片段。
    """
    # 统一单会话 Agent 的 system：最终回答优先 + 工具调用准则（balanced）。
    # 保留原函数签名与 fragment 注入行为，避免影响上层调用点。
    parts: list[str] = [system_prompt_for_chat_session_template.render()]

    fragment = user_context_system_fragment_template.render(
        user_memories=user_memories or [],
        window_out_summary=window_out_summary,
    ).strip()
    if fragment:
        parts.append(fragment)

    return "\n\n".join(parts)


def get_system_prompt_for_title() -> str:
    """Get system prompt for title generation"""
    return system_prompt_for_title_template.render().strip()


def get_user_message_for_tool_calls(
    user_message_text: str,
    mcp_auto_mode: bool,
    server_names: list[str],
    client_ip: str | None,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message prompt for tool calls.

    attachments: 可选，每项建议包含 file_id、file_name、text（与 user_prompt 模板一致）。
    """
    id_by_config = {config["id"]: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [
        id_by_config[server_name]
        for server_name in server_names
        if server_name in id_by_config
    ]

    return user_message_for_tool_call_template.render(
        user_message_text=user_message_text,
        attachments=attachments or [],
        mcp_auto_mode=mcp_auto_mode,
        mcp_configs=mcp_configs,
        current_datetime=get_current_datetime_str(),
        client_ip=client_ip,
    ).strip()


def get_user_message_for_title(
    user_message_text: str,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message prompt for title generation.

    仅使用至多 1 条附件（取列表首项，调用方宜传入已按相关性排序的 top-k）。
    """
    return user_message_for_default_template.render(
        user_message_text=user_message_text,
        attachments=(attachments or [])[:1],
    ).strip()


def get_window_out_summary_merge_prompt(
    prior_summary: str,
    new_messages_text: str,
    max_tokens: int,
) -> str:
    """渲染窗口外合并摘要的 prompt（已有摘要 + 新增消息内容 → 合并摘要）。"""
    return WINDOW_OUT_SUMMARY_MERGE_PROMPT.render(
        prior_summary=prior_summary,
        new_messages_text=new_messages_text,
        max_tokens_hint=max_tokens,
    ).strip()


def get_prompt_for_title(
    user_input: str | list[ContentBlock] | list[dict[str, Any]],
) -> tuple[str, str | list[dict[str, Any]]]:
    """Get combined system prompt and user message for title generation.

    Pass a string for text-only, or content blocks to include images in the user message.
    """
    from app.utils.multimodal import build_title_user_message_for_llm

    system_prompt = get_system_prompt_for_title().strip()
    if isinstance(user_input, str):
        return system_prompt, get_user_message_for_title(user_input)
    user_message_prompt = build_title_user_message_for_llm(user_input)
    return system_prompt, user_message_prompt


def get_disabled_tools_message(disabled_tools: list[str]) -> str:
    """Get disabled tools message"""
    return disabled_tools_message_template.render(disabled_tools=disabled_tools).strip()


def get_gentle_tips_in_web_search() -> str:
    """Get gentle tips in web search"""
    return gentle_tips_in_web_search_template.render().strip()


def get_tool_call_sufficient_info_message() -> str:
    """Get message when sufficient info may have been obtained"""
    return tool_call_sufficient_info_template.render().strip()


def get_user_message_for_reach_tool_call_limit(
    user_message: str,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message for reach tool call limit"""
    return user_message_for_reach_tool_call_limit_template.render(
        user_message_text=user_message,
        attachments=attachments or [],
    ).strip()


def get_user_message_for_no_tool_call(
    user_message: str,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Get user message for no tool call"""
    return user_message_for_no_tool_call_template.render(
        user_message_text=user_message,
        attachments=attachments or [],
    ).strip()

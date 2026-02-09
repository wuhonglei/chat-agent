"""提示词工具函数模块"""

from typing import Any

from app.mcp.mcp_client import mcp_config_for_fe
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_component_render_template,
    system_prompt_for_response_generation_template,
    system_prompt_for_title_template,
    system_prompt_for_tool_calls_template,
    user_context_system_fragment_template,
)
from app.prompts.user_prompt import (
    WINDOW_OUT_SUMMARY_MERGE_PROMPT,
    WINDOW_OUT_SUMMARY_PROMPT,
    component_data_block_template,
    disabled_tools_message_template,
    final_response_message_template,
    gentle_tips_in_web_search_template,
    mcp_block_template,
    tool_call_sufficient_info_template,
    user_message_for_title_template,
    user_message_for_tool_call_template,
)
from app.utils.date import get_current_datetime_str


def get_default_system_prompt() -> str:
    """Get default system prompt with current time information"""
    return default_system_prompt_template.render()


def get_system_prompt_for_response_generation(
    user_memories: list[str] | None = None,
    window_out_summary: str | None = None,
) -> str:
    """Get system prompt for final response generation.
    当传入 user_memories / window_out_summary 时注入对应片段。
    """
    base = system_prompt_for_response_generation_template.render()
    fragment = user_context_system_fragment_template.render(
        user_memories=user_memories or [],
        window_out_summary=window_out_summary,
    )
    if not fragment.strip():
        return base

    return "\n\n".join([base, fragment.strip()])


def get_system_prompt_for_tool_calls() -> str:
    """Get system prompt for tool calls"""
    return system_prompt_for_tool_calls_template.render().strip()


def get_system_prompt_for_title() -> str:
    """Get system prompt for title generation"""
    return system_prompt_for_title_template.render().strip()


def get_user_message_for_tool_calls(
    user_message: str,
    mcp_auto_mode: bool,
    server_names: list[str],
    client_ip: str | None,
) -> str:
    """Get user message prompt for tool calls"""
    id_by_config = {config["id"]: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [
        id_by_config[server_name]
        for server_name in server_names
        if server_name in id_by_config
    ]

    return user_message_for_tool_call_template.render(
        user_message=user_message,
        mcp_auto_mode=mcp_auto_mode,
        mcp_configs=mcp_configs,
        current_datetime=get_current_datetime_str(),
        client_ip=client_ip,
    ).strip()


def get_user_message_for_title(user_message: str) -> str:
    """Get user message prompt for title generation"""
    return user_message_for_title_template.render(user_message=user_message)


def get_window_out_summary_prompt(
    text: str,
    max_tokens: int,
) -> str:
    """渲染窗口外摘要的 prompt（用于对截断的旧消息生成简短摘要）。"""
    return WINDOW_OUT_SUMMARY_PROMPT.render(
        max_tokens_hint=max_tokens,
        text=text,
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


def get_prompt_with_mcp_servers(
    user_message: str,
    mcp_auto_mode: bool,
    server_names: list[str],
    client_ip: str | None,
) -> tuple[str, str]:
    """Get combined system prompt and user message for tool calls with MCP servers"""
    system_prompt = get_system_prompt_for_tool_calls().strip()
    user_message_prompt = get_user_message_for_tool_calls(
        user_message, mcp_auto_mode, server_names, client_ip
    )
    return system_prompt, user_message_prompt


def get_prompt_for_title(user_message: str) -> tuple[str, str]:
    """Get combined system prompt and user message for title generation"""
    system_prompt = get_system_prompt_for_title().strip()
    user_message_prompt = get_user_message_for_title(user_message)
    return system_prompt, user_message_prompt


def get_prompt_for_component_render_data(
    user_message: str,
) -> tuple[str, str]:
    """Get combined system prompt and user message for component render"""
    system_prompt = system_prompt_for_component_render_template.render().strip()
    return system_prompt, user_message


def get_disabled_tools_message(disabled_tools: list[str]) -> str:
    """Get disabled tools message"""
    return disabled_tools_message_template.render(disabled_tools=disabled_tools).strip()


def get_gentle_tips_in_web_search() -> str:
    """Get gentle tips in web search"""
    return gentle_tips_in_web_search_template.render().strip()


def get_tool_call_sufficient_info_message() -> str:
    """Get message when sufficient info may have been obtained"""
    return tool_call_sufficient_info_template.render().strip()


def get_user_message_combine_tool_calls(
    user_message: str,
    mcp_tool_items: list[dict[str, str]],
    component_data: list[dict[str, Any]],
) -> str:
    """Get user message for response generation"""
    return final_response_message_template.render(
        tool_result=mcp_block_template.render(mcp_tool_items=mcp_tool_items),
        component_data=component_data_block_template.render(
            component_data=component_data
        ),
        user_message=user_message,
    ).strip()

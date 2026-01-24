"""提示词工具函数模块"""

from app.mcp.mcp_client import mcp_config_for_fe
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_component_render_template,
    system_prompt_for_response_generation_template,
    system_prompt_for_title_template,
    system_prompt_for_tool_calls_template,
)
from app.prompts.user_prompt import (
    component_data_block_template,
    disabled_tools_message_template,
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


def get_system_prompt_for_response_generation(has_tool_calls: bool = False) -> str:
    """Get system prompt for final response generation.

    When has_tool_calls=True: 增加禁止 DSML、负向示例与兜底规则，避免模型延续 tool_calls 样式。
    When has_tool_calls=False: 仅保留基础规则，不注入 DSML 相关提示。
    """
    return system_prompt_for_response_generation_template.render(
        has_tool_calls=has_tool_calls
    )


def get_system_prompt_for_tool_calls() -> str:
    """Get system prompt for tool calls"""
    return system_prompt_for_tool_calls_template.render()


def get_system_prompt_for_title() -> str:
    """Get system prompt for title generation"""
    return system_prompt_for_title_template.render()


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
    )


def get_user_message_for_title(user_message: str) -> str:
    """Get user message prompt for title generation"""
    return user_message_for_title_template.render(user_message=user_message)


def get_prompt_with_mcp_servers(
    user_message: str,
    mcp_auto_mode: bool,
    server_names: list[str],
    client_ip: str | None,
) -> tuple[str, str]:
    """Get combined system prompt and user message for tool calls with MCP servers"""
    system_prompt = get_system_prompt_for_tool_calls()
    user_message_prompt = get_user_message_for_tool_calls(
        user_message, mcp_auto_mode, server_names, client_ip
    )
    return system_prompt, user_message_prompt


def get_prompt_for_title(user_message: str) -> tuple[str, str]:
    """Get combined system prompt and user message for title generation"""
    system_prompt = get_system_prompt_for_title()
    user_message_prompt = get_user_message_for_title(user_message)
    return system_prompt, user_message_prompt


def get_prompt_for_component_render_data(
    user_message: str,
) -> tuple[str, str]:
    """Get combined system prompt and user message for component render"""
    system_prompt = system_prompt_for_component_render_template.render()
    return system_prompt, user_message


def get_disabled_tools_message(disabled_tools: list[str]) -> str:
    """Get disabled tools message"""
    return disabled_tools_message_template.render(disabled_tools=disabled_tools)


def get_gentle_tips_in_web_search():
    """Get gentle tips in web search"""
    return gentle_tips_in_web_search_template.render()


def get_tool_call_sufficient_info_message():
    """Get message when sufficient info may have been obtained"""
    return tool_call_sufficient_info_template.render()


def get_user_message_for_response_generation(
    user_message: str,
    component_data: list[dict],
    mcp_tool_items: list[dict[str, str]],
) -> str:
    """Get user message for response generation"""
    parts = [
        user_message,
    ]
    if mcp_tool_items:
        parts.append(mcp_block_template.render(mcp_tool_items=mcp_tool_items))
    if component_data:
        parts.append(
            component_data_block_template.render(component_data=component_data)
        )
    return "\n\n".join(parts)

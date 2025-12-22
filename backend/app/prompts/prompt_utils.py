"""提示词工具函数模块"""
import json

from app.mcp.mcp_client import mcp_config_for_fe
from app.prompts.system_prompt import (
    default_system_prompt_template,
    system_prompt_for_component_render_template,
    system_prompt_for_tool_calls_template,
    system_prompt_for_title_template,
)
from app.prompts.user_prompt import (
    user_message_for_tool_call_template,
    user_message_for_title_template,
)
from app.schemas.llm import ToolCallMessage
from app.utils.date import get_current_date, get_current_datetime_str


def get_default_system_prompt(include_date: bool = False) -> str:
    """Get default system prompt with current time information"""
    if include_date:
        current_datetime = get_current_datetime_str()
        current_date = get_current_date()
        return default_system_prompt_template.render(current_datetime=current_datetime, current_date=current_date)
    else:
        return default_system_prompt_template.render()


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
    client_ip: str | None
) -> str:
    """Get user message prompt for tool calls"""
    id_by_config = {config['id']: config for config in mcp_config_for_fe}
    server_names = server_names or []
    mcp_configs = [id_by_config[server_name]
                   for server_name in server_names if server_name in id_by_config]

    return user_message_for_tool_call_template.render(
        user_message=user_message,
        mcp_auto_mode=mcp_auto_mode,
        mcp_configs=mcp_configs,
        current_datetime=get_current_datetime_str(),
        client_ip=client_ip
    )


def get_user_message_for_title(user_message: str) -> str:
    """Get user message prompt for title generation"""
    return user_message_for_title_template.render(
        user_message=user_message
    )


def get_prompt_with_mcp_servers(
    user_message: str,
    mcp_auto_mode: bool,
    server_names: list[str],
    client_ip: str | None
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


def get_user_message_with_component_data(
    user_message: str,
    component_tool_call_messages: list[ToolCallMessage],
) -> str:
    """Get user message with component data"""
    if not component_tool_call_messages:
        return user_message

    component_data = []
    for tool_call_message in component_tool_call_messages:
        component_data.append({
            'component_name': tool_call_message.tool_call.name,
            'props': tool_call_message.tool_call.arguments,
        })

    # return user_message_with_component_data_template.render(
    #     user_message=user_message,
    #     component_tool_call_messages=component_tool_call_messages,
    # )

from typing import Any

import httpx
from mcp.shared._httpx_utils import McpHttpClientFactory

from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)


def create_mcp_http_client_with_ssl_config(
    verify_ssl: bool = True,
) -> McpHttpClientFactory:
    """创建支持 SSL 验证配置的 MCP HTTP 客户端工厂"""

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        # 使用 MCP 默认配置，但添加 SSL 验证控制
        kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "verify": verify_ssl,  # 控制 SSL 证书验证
        }

        # Handle timeout
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0)
        else:
            kwargs["timeout"] = timeout

        # Handle headers
        if headers is not None:
            kwargs["headers"] = headers

        # Handle authentication
        if auth is not None:
            kwargs["auth"] = auth

        return httpx.AsyncClient(**kwargs)

    return factory


def extract_tool_call_names(output_messages: list[ToolCallMessage]) -> list[str]:
    """
    从收集的工具调用消息中提取工具名称列表

    Args:
        output_messages: 工具调用消息列表

    Returns:
        list[str]: 工具名称列表
    """
    tool_names = []
    for message in output_messages:
        if isinstance(message, AssistantToolCallMessage) and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_names.append(tool_call.function.name)
    return tool_names


def count_tool_calls(output_messages: list[ToolCallMessage]) -> int:
    """
    统计工具调用结果消息的数量

    Args:
        output_messages: 工具调用消息列表

    Returns:
        int: 工具调用结果消息的数量
    """
    return len([m for m in output_messages if isinstance(m, ToolCallResultMessage)])

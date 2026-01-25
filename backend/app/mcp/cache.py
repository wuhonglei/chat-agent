"""MCP 工具调用结果缓存：基于 ResponseCachingMiddleware 与 DiskStore 的工厂。"""

from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from key_value.aio.stores.disk import DiskStore

from app.schemas.config import MCPCacheConfig


def add_response_caching_if_enabled(mcp: FastMCP, cache_config: MCPCacheConfig) -> None:
    """
    若 cache_config.cache_enabled 为 True，则为 mcp 添加 ResponseCachingMiddleware。
    否则不添加。封装「读取 cache_config → 判断 enabled → 创建并 add_middleware」整段逻辑。
    """
    if cache_config.cache_enabled:
        mcp.add_middleware(
            create_response_caching_middleware(
                cache_dir=cache_config.cache_dir,
                call_tool_ttl=cache_config.call_tool_ttl,
                call_tool_excluded=cache_config.call_tool_excluded,
            )
        )


def create_response_caching_middleware(
    cache_dir: str,
    *,
    call_tool_ttl: int = 300,
    call_tool_excluded: list[str] | None = None,
    list_tools_enabled: bool = True,
    max_item_size: int = 1048576,
) -> ResponseCachingMiddleware:
    """
    创建 MCP 工具调用结果缓存的 ResponseCachingMiddleware。

    - 使用 DiskStore 持久化到 cache_dir；创建前会 mkdir(parents=True, exist_ok=True)。
    - 仅缓存 tools/call，list_tools / list_resources / list_prompts / read_resource / get_prompt 默认不缓存。
    - call_tool 的 excluded_tools 默认为 ["python_code_exec"]，避免缓存代码执行结果。

    Args:
        cache_dir: DiskStore 存储目录。
        call_tool_ttl: 工具调用缓存 TTL（秒）。
        call_tool_excluded: 不缓存的工具名列表；为 None 时使用 ["python_code_exec"]。
        list_tools_enabled: 是否缓存 list_tools / list_resources / list_prompts / read_resource / get_prompt。
        max_item_size: 单条缓存最大字节数。

    Returns:
        ResponseCachingMiddleware 实例。
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    excluded = (
        call_tool_excluded if call_tool_excluded is not None else ["python_code_exec"]
    )

    return ResponseCachingMiddleware(
        cache_storage=DiskStore(directory=cache_dir),
        call_tool_settings={
            "enabled": True,
            "ttl": call_tool_ttl,
            "excluded_tools": excluded,
        },
        list_tools_settings={"enabled": list_tools_enabled},
        list_resources_settings={"enabled": list_tools_enabled},
        list_prompts_settings={"enabled": list_tools_enabled},
        read_resource_settings={"enabled": list_tools_enabled},
        get_prompt_settings={"enabled": list_tools_enabled},
        max_item_size=max_item_size,
    )

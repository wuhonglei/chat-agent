"""MCP 工具调用结果缓存：基于 ResponseCachingMiddleware 与 FileTreeStore 的工厂。"""

import json
import shutil
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ResponseCachingMiddleware,
)
from key_value.aio.stores.filetree import (
    FileTreeStore,
    FileTreeV1KeySanitizationStrategy,
)

from app.schemas.config import MCPCacheConfig
from app.utils.logger import logger


def _cleanup_stale_filetree_cache(cache_path: Path) -> None:
    """
    FileTreeStore 会读取现有的 `{collection}-info.json` 并信任其中的 `directory` 字段。

    当项目目录从 `ai-doc` 重命名到 `chat-agent` 后，旧缓存元数据里的 `directory`
    仍可能指向旧绝对路径，导致后续 put/get 时触发：
    `Path '.../ai-doc/.../tools/list/__global__.json' resolves outside the allowed directory ...`

    为避免 mcp 加载失败，这里检测到元数据目录越界时，直接清空当前 cache_path。
    """
    if not cache_path.exists():
        return

    try:
        allowed_root = cache_path.resolve(strict=False)
    except Exception:
        # 极端情况下 resolve 失败：直接放行（交由后续 mkdir/创建处理）
        return

    # 只需要检查 info 文件即可，因为它决定 collection 的实际目录。
    for info_file in cache_path.rglob("*-info.json"):
        try:
            raw = info_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            continue

        stored_dir = data.get("directory")
        if not stored_dir:
            continue

        try:
            stored_resolved = Path(stored_dir).resolve(strict=False)
        except Exception:
            continue

        if not (
            stored_resolved == allowed_root
            or stored_resolved.is_relative_to(allowed_root)
        ):
            logger.warning(
                "Stale MCP cache detected; clearing cache directory",
                cache_dir=str(cache_path),
                info_file=str(info_file),
                stale_directory=str(stored_dir),
                allowed_directory=str(allowed_root),
            )
            shutil.rmtree(cache_path, ignore_errors=True)
            return


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

    - 使用 FileTreeStore 持久化到 cache_dir（基于 JSON 文件，规避 diskcache CVE 风险）；创建前会 mkdir(parents=True, exist_ok=True)。
    - 仅缓存 tools/call，list_tools / list_resources / list_prompts / read_resource / get_prompt 默认不缓存。
    - call_tool 的 excluded_tools 默认为 ["python_code_exec"]，避免缓存代码执行结果。

    Args:
        cache_dir: FileTreeStore 存储目录。
        call_tool_ttl: 工具调用缓存 TTL（秒）。
        call_tool_excluded: 不缓存的工具名列表；为 None 时使用 ["python_code_exec"]。
        list_tools_enabled: 是否缓存 list_tools / list_resources / list_prompts / read_resource / get_prompt。
        max_item_size: 单条缓存最大字节数。

    Returns:
        ResponseCachingMiddleware 实例。
    """
    cache_path = Path(cache_dir).resolve()
    _cleanup_stale_filetree_cache(cache_path)
    cache_path.mkdir(parents=True, exist_ok=True)

    excluded_tools: list[str] = (
        call_tool_excluded if call_tool_excluded is not None else ["python_code_exec"]
    )
    call_tool_settings: CallToolSettings = {
        "enabled": True,
        "ttl": call_tool_ttl,
        "excluded_tools": excluded_tools,
    }
    return ResponseCachingMiddleware(
        cache_storage=FileTreeStore(
            data_directory=cache_path,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(
                directory=cache_path
            ),
        ),
        call_tool_settings=call_tool_settings,
        list_tools_settings={"enabled": list_tools_enabled},
        list_resources_settings={"enabled": list_tools_enabled},
        list_prompts_settings={"enabled": list_tools_enabled},
        read_resource_settings={"enabled": list_tools_enabled},
        get_prompt_settings={"enabled": list_tools_enabled},
        max_item_size=max_item_size,
    )

"""Subtract ``excluded_tools`` from a parent tool surface.

Entries are either a canonical LLM name (``{server}_{bare}``) or a server
wildcard (``{server}_*``), matched by route rather than string prefix.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from app.core.config import settings
from app.mcp.tool_naming import ToolRoute, llm_tool_name
from app.utils.logger import logger

_WILDCARD_SUFFIX = "_*"
ExcludedEntryStatus = Literal["ok", "error", "warn"]


class ExcludedToolConfigError(RuntimeError):
    """``excluded_tools`` contains a bare name or alias that would silently miss."""


def server_wildcard_name(entry: str) -> str | None:
    """Return the server key for ``{server}_*``, or None for other shapes."""
    if not entry.endswith(_WILDCARD_SUFFIX):
        return None
    server_name = entry[: -len(_WILDCARD_SUFFIX)]
    if not server_name or "*" in server_name:
        return None
    return server_name


def classify_excluded_entry(
    entry: str,
    *,
    get_tool_route: Callable[[str], ToolRoute | None],
    registered_servers: set[str],
) -> ExcludedEntryStatus:
    server_name = server_wildcard_name(entry)
    if server_name is not None:
        if server_name in registered_servers:
            return "ok"
        return "warn"
    route = get_tool_route(entry)
    if route is None:
        return "warn"
    canonical = llm_tool_name(route.server_name, route.mcp_tool_name)
    if entry == canonical:
        return "ok"
    return "error"


def validate_excluded_tools(
    *,
    get_tool_route: Callable[[str], ToolRoute | None],
    registered_servers: set[str],
) -> None:
    """Check ``subagent.excluded_tools`` after the tool index exists.

    Bare names and aliases fail startup. Unknown names are kept and logged.
    """
    errors: list[str] = []
    for entry in settings.subagent.excluded_tools:
        status = classify_excluded_entry(
            entry,
            get_tool_route=get_tool_route,
            registered_servers=registered_servers,
        )
        if status == "ok":
            continue
        if status == "warn":
            logger.warning(
                "subagent.excluded_tools entry is unknown and will be kept",
                entry=entry,
            )
            continue
        route = get_tool_route(entry)
        if route is None:
            errors.append(
                f'{entry!r} 不是规范工具名。请使用 {{server}}_{{bare}} 或 "{{server}}_*"。'
            )
            continue
        canonical = llm_tool_name(route.server_name, route.mcp_tool_name)
        errors.append(
            f"{entry!r} 不是规范工具名。请改成 {canonical!r}，"
            f'或使用 server 级 "{route.server_name}_*"。'
        )
    if errors:
        raise ExcludedToolConfigError(
            "subagent.excluded_tools 配置非法: " + "; ".join(errors)
        )


def is_llm_tool_excluded(
    llm_name: str,
    excluded_tools: list[str],
    get_tool_route: Callable[[str], ToolRoute | None],
) -> bool:
    route = get_tool_route(llm_name)
    server_name = route.server_name if route is not None else None
    for entry in excluded_tools:
        wildcard = server_wildcard_name(entry)
        if wildcard is not None:
            if server_name == wildcard:
                return True
            continue
        if entry != llm_name:
            continue
        if route is None:
            return True
        canonical = llm_tool_name(route.server_name, route.mcp_tool_name)
        if entry == canonical:
            return True
    return False


def filter_llm_tools(
    tools: list[dict[str, Any]],
    excluded_tools: list[str],
    get_tool_route: Callable[[str], ToolRoute | None],
) -> list[dict[str, Any]]:
    if not excluded_tools:
        return list(tools)
    kept: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function")
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str):
            kept.append(tool)
            continue
        if is_llm_tool_excluded(name, excluded_tools, get_tool_route):
            continue
        kept.append(tool)
    return kept

"""LLM / MCP dual-track tool naming helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolRoute:
    """Resolved routing from an LLM-visible tool name to MCP."""

    server_name: str
    mcp_tool_name: str


def llm_tool_name(server_name: str, bare_name: str) -> str:
    """Build the name exposed to the LLM: ``{server_name}_{bare_name}``."""
    return f"{server_name}_{bare_name}"


def to_mcp_tool_name(llm_name: str, server_name: str) -> str:
    """Strip server prefix when calling MCP (best-effort)."""
    prefix = f"{server_name}_"
    if llm_name.startswith(prefix):
        return llm_name[len(prefix) :]
    return llm_name


def is_llm_tool(llm_name: str, server_name: str, bare_name: str) -> bool:
    return llm_name == llm_tool_name(server_name, bare_name)


def resolve_server_by_prefix(llm_name: str, server_names: Iterable[str]) -> str | None:
    candidates = [name for name in server_names if llm_name.startswith(f"{name}_")]
    if not candidates:
        return None
    return max(candidates, key=len)


def bare_tool_name(llm_name: str, server_names: Iterable[str]) -> str:
    server = resolve_server_by_prefix(llm_name, server_names)
    if server is None:
        return llm_name
    return to_mcp_tool_name(llm_name, server)


def resolve_tool_use_fields(
    llm_name: str,
    get_tool_route: Callable[[str], ToolRoute | None],
) -> tuple[str, str, str]:
    """Return ``(name, server_name, mcp_tool_name)`` for a ToolUseBlock enrich."""
    route = get_tool_route(llm_name)
    if not route:
        raise ValueError(f"未知工具名: {llm_name}")
    return llm_name, route.server_name, route.mcp_tool_name

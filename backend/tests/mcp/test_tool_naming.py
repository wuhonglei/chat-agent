"""Tests for MCP LLM/MCP dual-track tool naming."""

from __future__ import annotations

import pytest

from app.mcp.tool_naming import (
    ToolRoute,
    bare_tool_name,
    is_llm_tool,
    llm_tool_name,
    resolve_server_by_prefix,
    to_mcp_tool_name,
)


def test_llm_tool_name_and_strip() -> None:
    assert llm_tool_name("tavily", "web_search") == "tavily_web_search"
    assert to_mcp_tool_name("tavily_web_search", "tavily") == "web_search"


def test_deerflow_style_github_search() -> None:
    assert llm_tool_name("github", "search") == "github_search"
    assert to_mcp_tool_name("github_search", "github") == "search"


def test_is_llm_tool() -> None:
    assert is_llm_tool("tavily_web_search", "tavily", "web_search")
    assert not is_llm_tool("web_search", "tavily", "web_search")


def test_bare_name_without_prefix_unchanged() -> None:
    assert to_mcp_tool_name("web_search", "tavily") == "web_search"


def test_code_server_tool_naming() -> None:
    assert llm_tool_name("code", "execute_code") == "code_execute_code"
    assert to_mcp_tool_name("code_execute_code", "code") == "execute_code"


def test_resolve_server_by_prefix() -> None:
    servers = ["code", "context7", "tavily"]
    assert resolve_server_by_prefix("code_execute_code", servers) == "code"
    assert resolve_server_by_prefix("tavily_web_search", servers) == "tavily"
    assert resolve_server_by_prefix("web_search", servers) is None


def test_bare_tool_name() -> None:
    servers = ["tavily", "file"]
    assert bare_tool_name("tavily_web_search", servers) == "web_search"
    assert bare_tool_name("unknown_tool", servers) == "unknown_tool"


def test_tool_name_with_internal_underscore() -> None:
    llm = llm_tool_name("context7", "resolve-library-id")
    assert to_mcp_tool_name(llm, "context7") == "resolve-library-id"


def test_resolve_tool_use_fields() -> None:
    from app.mcp.tool_naming import resolve_tool_use_fields

    def lookup(name: str) -> ToolRoute | None:
        if name == "tavily_web_search":
            return ToolRoute(server_name="tavily", mcp_tool_name="web_search")
        return None

    name, server, mcp = resolve_tool_use_fields("tavily_web_search", lookup)
    assert name == "tavily_web_search"
    assert server == "tavily"
    assert mcp == "web_search"


def test_resolve_tool_use_fields_prefixed_name() -> None:
    from app.mcp.tool_naming import resolve_tool_use_fields

    def lookup(name: str) -> ToolRoute | None:
        if name == "skill_manager_load_skill":
            return ToolRoute(server_name="skill_manager", mcp_tool_name="load_skill")
        return None

    name, server, mcp = resolve_tool_use_fields("skill_manager_load_skill", lookup)
    assert name == "skill_manager_load_skill"
    assert server == "skill_manager"
    assert mcp == "load_skill"


def test_resolve_tool_use_fields_unknown_raises() -> None:
    from app.mcp.tool_naming import resolve_tool_use_fields

    with pytest.raises(ValueError, match="未知工具名"):
        resolve_tool_use_fields("missing_tool", lambda _n: None)


def test_resolve_tool_use_fields_canonicalizes_bare_alias() -> None:
    from app.mcp.tool_naming import resolve_tool_use_fields

    def lookup(name: str) -> ToolRoute | None:
        if name in {"present_files", "file_present_files"}:
            return ToolRoute(server_name="file", mcp_tool_name="present_files")
        return None

    name, server, mcp = resolve_tool_use_fields("present_files", lookup)
    assert name == "file_present_files"
    assert server == "file"
    assert mcp == "present_files"

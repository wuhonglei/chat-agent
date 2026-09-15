"""Unit tests for MCP server/tool constants."""

from __future__ import annotations

from app.mcp.constants import (
    FILE_SERVER,
    MUTATING_LLM_TOOLS,
    PATH_SCOPED_FILE_BARE_TOOLS,
    PUBLISH_SITE_BARE,
    PUBLISH_SITE_LLM,
    SHELL_SERVER,
    SKILL_MANAGER_SERVER,
    SKIP_TOOL_RESULT_COMPACTION_SERVERS,
    TAVILY_SERVER,
    WEB_PAGES_EXTRACT_BARE,
    WEB_PAGES_EXTRACT_LLM,
    WEB_SEARCH_BARE,
    WEB_SEARCH_LLM,
)
from app.mcp.tool_naming import llm_tool_name


def test_web_search_llm_name() -> None:
    assert WEB_SEARCH_LLM == llm_tool_name(TAVILY_SERVER, WEB_SEARCH_BARE)
    assert WEB_SEARCH_LLM == "tavily_web_search"


def test_web_pages_extract_llm_name() -> None:
    assert WEB_PAGES_EXTRACT_LLM == llm_tool_name(
        TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE
    )


def test_skip_compaction_servers() -> None:
    assert FILE_SERVER in SKIP_TOOL_RESULT_COMPACTION_SERVERS
    assert SHELL_SERVER in SKIP_TOOL_RESULT_COMPACTION_SERVERS
    assert SKILL_MANAGER_SERVER in SKIP_TOOL_RESULT_COMPACTION_SERVERS


def test_publish_site_is_mutating() -> None:
    assert PUBLISH_SITE_LLM == "file_publish_site"
    assert PUBLISH_SITE_LLM in MUTATING_LLM_TOOLS
    assert PUBLISH_SITE_BARE not in PATH_SCOPED_FILE_BARE_TOOLS

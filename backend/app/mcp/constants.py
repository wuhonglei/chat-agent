"""MCP server keys and bare tool names (must match mcp_servers config and @mcp.tool names)."""

from __future__ import annotations

from app.mcp.tool_naming import llm_tool_name

# --- MCP server keys (= mcp_servers config keys) ---
TAVILY_SERVER = "tavily"
FILE_SERVER = "file"
SKILL_MANAGER_SERVER = "skill_manager"
SHELL_SERVER = "shell"
CODE_EXEC_SERVER = "code-exec"

# --- Tavily bare tools (agent layer) ---
WEB_SEARCH_BARE = "web_search"
WEB_PAGES_EXTRACT_BARE = "web_pages_extract"
WEB_SITE_CRAWL_BARE = "web_site_crawl"

# --- Precomputed LLM names (policy / history keys) ---
WEB_SEARCH_LLM = llm_tool_name(TAVILY_SERVER, WEB_SEARCH_BARE)
WEB_PAGES_EXTRACT_LLM = llm_tool_name(TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE)

# --- Policy sets ---
SKIP_TOOL_RESULT_COMPACTION_SERVERS = frozenset({FILE_SERVER, SHELL_SERVER})

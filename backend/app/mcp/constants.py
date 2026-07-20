"""MCP server keys and bare tool names (must match mcp_servers config and @mcp.tool names)."""

from __future__ import annotations

from app.mcp.tool_naming import llm_tool_name

# --- MCP server keys (= mcp_servers config keys) ---
TAVILY_SERVER = "tavily"
FILE_SERVER = "file"
SKILL_MANAGER_SERVER = "skill_manager"
SHELL_SERVER = "shell"
CODE_SERVER = "code"
WEATHER_SERVER = "weather"
TIME_SERVER = "time"

# --- File MCP bare tools ---
READ_FILE_BARE = "read_file"
WRITE_FILE_BARE = "write_file"
EDIT_FILE_BARE = "edit_file"
SEARCH_FILES_BARE = "search_files"
PRESENT_FILES_BARE = "present_files"

# --- Shell / code bare tools ---
SHELL_BARE = "shell"
EXECUTE_CODE_BARE = "execute_code"
LIST_RUNTIMES_BARE = "list_runtimes"

# --- Tavily bare tools (agent layer) ---
WEB_SEARCH_BARE = "web_search"
WEB_PAGES_EXTRACT_BARE = "web_pages_extract"
WEB_SITE_CRAWL_BARE = "web_site_crawl"

# --- Precomputed LLM names (policy / history keys) ---
WEB_SEARCH_LLM = llm_tool_name(TAVILY_SERVER, WEB_SEARCH_BARE)
WEB_PAGES_EXTRACT_LLM = llm_tool_name(TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE)

READ_FILE_LLM = llm_tool_name(FILE_SERVER, READ_FILE_BARE)
WRITE_FILE_LLM = llm_tool_name(FILE_SERVER, WRITE_FILE_BARE)
EDIT_FILE_LLM = llm_tool_name(FILE_SERVER, EDIT_FILE_BARE)
SEARCH_FILES_LLM = llm_tool_name(FILE_SERVER, SEARCH_FILES_BARE)
PRESENT_FILES_LLM = llm_tool_name(FILE_SERVER, PRESENT_FILES_BARE)
SHELL_LLM = llm_tool_name(SHELL_SERVER, SHELL_BARE)
EXECUTE_CODE_LLM = llm_tool_name(CODE_SERVER, EXECUTE_CODE_BARE)
LIST_RUNTIMES_LLM = llm_tool_name(CODE_SERVER, LIST_RUNTIMES_BARE)

# Path-scoped file tools for parallel batch planning
PATH_SCOPED_FILE_BARE_TOOLS = frozenset(
    {
        READ_FILE_BARE,
        WRITE_FILE_BARE,
        EDIT_FILE_BARE,
        PRESENT_FILES_BARE,
    }
)

# Guardrail: idempotent (read-only) vs mutating (side effects)
IDEMPOTENT_LLM_TOOLS = frozenset(
    {
        READ_FILE_LLM,
        SEARCH_FILES_LLM,
        WEB_SEARCH_LLM,
        WEB_PAGES_EXTRACT_LLM,
        llm_tool_name(TAVILY_SERVER, WEB_SITE_CRAWL_BARE),
        LIST_RUNTIMES_LLM,
        llm_tool_name(TIME_SERVER, "get_current_time"),
        llm_tool_name(WEATHER_SERVER, "search_city"),
        llm_tool_name(WEATHER_SERVER, "get_current_weather"),
        llm_tool_name(WEATHER_SERVER, "get_weather_hourly_forecast"),
        llm_tool_name(WEATHER_SERVER, "get_weather_daily_forecast"),
        llm_tool_name(WEATHER_SERVER, "get_weather_alerts"),
        llm_tool_name(SKILL_MANAGER_SERVER, "load_skill"),
    }
)

MUTATING_LLM_TOOLS = frozenset(
    {
        WRITE_FILE_LLM,
        EDIT_FILE_LLM,
        PRESENT_FILES_LLM,
        SHELL_LLM,
        EXECUTE_CODE_LLM,
    }
)

# --- Policy sets ---
SKIP_TOOL_RESULT_COMPACTION_SERVERS = frozenset({FILE_SERVER, SHELL_SERVER})

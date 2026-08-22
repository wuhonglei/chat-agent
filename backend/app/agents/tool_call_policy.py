"""Policy checks for tool-call iteration control."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.mcp.constants import (
    TAVILY_SERVER,
    WEB_PAGES_EXTRACT_BARE,
    WEB_PAGES_EXTRACT_LLM,
    WEB_SEARCH_LLM,
)
from app.mcp.tool_naming import is_llm_tool
from app.schemas.llm import ToolMessage
from app.utils.common import normalize_url
from app.utils.mcp import has_tool_been_called


class ToolCallPolicy:
    """Manage tool iteration limits."""

    MAX_WEB_SEARCH_COUNT = 2
    MAX_WEB_PAGES_EXTRACT_COUNT = 2
    EXTRACTED_URLS_HINT_THRESHOLD = 3
    MAX_EXTRACTED_URLS = 5

    def __init__(self, tool_round_messages: list[ToolMessage]) -> None:
        self.tool_round_messages = tool_round_messages
        self.tool_arguments_history_by_name: dict[str, list[dict[str, Any]]] = (
            defaultdict(list)
        )
        self.extracted_urls: set[str] = set()
        self._pending_iteration_hints: str | None = None

    def reset_for_request(self) -> None:
        self.extracted_urls = set()
        self.tool_arguments_history_by_name.clear()
        self._pending_iteration_hints = None

    def collect_iteration_hints(self) -> str | None:
        """按当前搜索/URL 状态收集 hints（不改写已有消息）。"""
        hint_messages: list[str] = []
        if has_tool_been_called(
            [(TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE)], self.tool_round_messages
        ) and (len(self.extracted_urls) >= self.EXTRACTED_URLS_HINT_THRESHOLD):
            hint_messages.append(
                f"已提取 {len(self.extracted_urls)} 个 URL，内容可能已足够，直接回答。"
            )
        web_search_count = len(
            self.tool_arguments_history_by_name.get(WEB_SEARCH_LLM, [])
        )
        web_pages_extract_count = len(
            self.tool_arguments_history_by_name.get(WEB_PAGES_EXTRACT_LLM, [])
        )
        if web_search_count >= self.MAX_WEB_SEARCH_COUNT:
            hint_messages.append(
                f"已执行 {web_search_count} 次搜索，结果可能已足够，直接回答。"
            )
        elif web_pages_extract_count >= self.MAX_WEB_PAGES_EXTRACT_COUNT:
            hint_messages.append(
                f"已执行 {web_pages_extract_count} 次网页提取，内容可能已足够，直接回答。"
            )
        elif len(self.extracted_urls) >= self.MAX_EXTRACTED_URLS:
            hint_messages.append(
                f"已提取 {len(self.extracted_urls)} 个 URL，内容可能已足够，直接回答。"
            )
        if not hint_messages:
            return None
        return "\n".join(hint_messages)

    def queue_iteration_hints_after_tools(self) -> None:
        """工具批次结束后重算并覆盖排队 hint，供下一轮 LLM 尾部消费。"""
        self._pending_iteration_hints = self.collect_iteration_hints()

    def drain_pending_iteration_hints(self) -> str | None:
        text = self._pending_iteration_hints
        self._pending_iteration_hints = None
        return text

    def record_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
        success: bool,
    ) -> None:
        self.tool_arguments_history_by_name[tool_name].append(
            {
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                "success": success,
            }
        )
        if success and is_llm_tool(tool_name, TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE):
            urls = arguments.get("urls")
            if isinstance(urls, list | set | tuple):
                self.extracted_urls.update(normalize_url(url) for url in urls if url)

    @staticmethod
    def matches_tavily_tool(tool_name: str, bare_name: str) -> bool:
        return is_llm_tool(tool_name, TAVILY_SERVER, bare_name)

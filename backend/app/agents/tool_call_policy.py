"""Policy checks for tool-call iteration control."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from toolz import get_in

from app.mcp.constants import (
    TAVILY_SERVER,
    WEB_PAGES_EXTRACT_BARE,
    WEB_PAGES_EXTRACT_LLM,
    WEB_SEARCH_LLM,
)
from app.mcp.tool_naming import is_llm_tool
from app.prompts import get_tool_call_sufficient_info_message
from app.schemas.llm import ToolMessage
from app.utils.common import normalize_url
from app.utils.mcp import count_tool_calls, has_tool_been_called
from app.utils.message import update_last_user_message
from app.utils.vocab import VocabProcessor


class ToolCallPolicy:
    """Manage tool iteration limits and duplicate-call heuristics."""

    QUERY_SIMILARITY_THRESHOLD = 0.7
    URL_OVERLAP_THRESHOLD = 0.7
    MIN_WEB_SEARCH_FOR_HINT = 1
    MIN_WEB_SEARCH_FOR_SIMILARITY_STOP = 1
    MAX_WEB_SEARCH_COUNT = 2
    MIN_WEB_PAGES_EXTRACT_FOR_OVERLAP_STOP = 1
    MAX_WEB_PAGES_EXTRACT_COUNT = 2
    EXTRACTED_URLS_HINT_THRESHOLD = 3
    MAX_EXTRACTED_URLS = 5
    MAX_TOTAL_TOOL_CALLS = 6
    MIN_ITERATION_FOR_HINT = 1

    def __init__(self, tool_round_messages: list[ToolMessage]) -> None:
        self.tool_round_messages = tool_round_messages
        self.tool_arguments_history_by_name: dict[str, list[dict[str, Any]]] = (
            defaultdict(list)
        )
        self.extracted_urls: set[str] = set()
        self.vocab_processor = VocabProcessor()

    def reset_for_request(self) -> None:
        self.extracted_urls = set()
        self.tool_arguments_history_by_name.clear()

    def apply_iteration_hints(
        self,
        *,
        messages: list[dict[str, Any]],
        tool_guided_user_message: str,
        iteration: int,
    ) -> None:
        hint_messages: list[str] = []
        web_search_count = len(self._get_web_search_queries())
        if (
            web_search_count >= self.MIN_WEB_SEARCH_FOR_HINT
            and iteration >= self.MIN_ITERATION_FOR_HINT
        ):
            hint_messages.append(
                "⚠️ 已执行过搜索，请先评估现有搜索结果是否足够回答用户问题。"
                "如果信息已充分，直接给出回答，不要再次调用工具。"
            )
        if has_tool_been_called(
            [(TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE)], self.tool_round_messages
        ) and (len(self.extracted_urls) >= self.EXTRACTED_URLS_HINT_THRESHOLD):
            hint_messages.append(
                f"⚠️ 已提取 {len(self.extracted_urls)} 个 URL，内容可能已足够，直接回答。"
            )
        should_continue, stop_reason_message = self.should_continue(None)
        if not should_continue:
            if stop_reason_message:
                hint_messages.append(stop_reason_message)
            if iteration >= self.MIN_ITERATION_FOR_HINT:
                hint_messages.append(get_tool_call_sufficient_info_message())
        if hint_messages:
            hints_text = "\n".join(hint_messages)
            update_last_user_message(
                messages,
                new_content=f"{tool_guided_user_message}\n\n注意:\n{hints_text}",
            )

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

    def _get_web_search_queries(self) -> list[str]:
        queries: list[str] = []
        for call_info in self.tool_arguments_history_by_name.get(WEB_SEARCH_LLM, []):
            if queries_list := get_in(["arguments", "queries"], call_info):
                if isinstance(queries_list, list):
                    queries.extend(str(q) for q in queries_list if q)
        return queries

    def _check_query_similarity(self, new_query: str) -> tuple[bool, float]:
        """检查新查询与历史网页搜索查询的相似度。

        遍历已记录的 web search queries，取与 ``new_query`` 的最高相似度；
        当最高相似度超过 ``QUERY_SIMILARITY_THRESHOLD`` 时判定为相似。

        Args:
            new_query: 待检查的新搜索查询文本。

        Returns:
            ``(is_similar, max_similarity)``：是否超过相似度阈值，以及历史查询中的最高相似度（0–1）。
            若尚无历史查询，返回 ``(False, 0.0)``。
        """
        web_search_queries = self._get_web_search_queries()
        if not web_search_queries:
            return False, 0.0
        max_similarity = 0.0
        for historical_query in web_search_queries:
            similarity = self.vocab_processor.calculate_query_similarity(
                new_query, historical_query
            )
            max_similarity = max(max_similarity, similarity)
        is_similar = max_similarity > self.QUERY_SIMILARITY_THRESHOLD
        return is_similar, max_similarity

    def _check_url_overlap(self, urls: list[str]) -> tuple[float, int]:
        """检查待提取 URL 与已提取 URL 的重叠程度。

        将 ``urls`` 规范化后与 ``self.extracted_urls`` 求交集，计算重叠比例与重叠数量。
        用于判断当前网页提取请求是否在重复提取已处理过的页面。

        Args:
            urls: 待检查的 URL 列表。

        Returns:
            ``(overlap_ratio, extracted_count)``：重叠比例（0–1），以及已提取过的 URL 数量。
            若 ``urls`` 为空，返回 ``(0.0, 0)``。
        """
        if not urls:
            return 0.0, 0
        normalized_urls = {normalize_url(url) for url in urls if url}
        extracted_count = len(normalized_urls & self.extracted_urls)
        overlap_ratio = (
            extracted_count / len(normalized_urls) if normalized_urls else 0.0
        )
        return overlap_ratio, extracted_count

    def _group_tool_call_arguments_by_name(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall]
    ) -> dict[str, list[dict[str, Any]]]:
        tool_arguments_by_name: dict[str, list[dict[str, Any]]] = {}
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, Exception):
                continue
            if tool_name not in tool_arguments_by_name:
                tool_arguments_by_name[tool_name] = []
            tool_arguments_by_name[tool_name].append(
                {
                    "arguments": arguments,
                    "tool_call_id": tool_call.id,
                }
            )
        return tool_arguments_by_name

    def should_continue(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall] | None
    ) -> tuple[bool, str | None]:
        web_search_count = len(self._get_web_search_queries())
        web_pages_extract_count = len(
            self.tool_arguments_history_by_name.get(WEB_PAGES_EXTRACT_LLM, [])
        )
        total_tool_calls = count_tool_calls(self.tool_round_messages)
        if tool_calls:
            tool_arguments_by_name = self._group_tool_call_arguments_by_name(tool_calls)
            for call_info in get_in([WEB_SEARCH_LLM], tool_arguments_by_name, []):
                queries = get_in(["arguments", "queries"], call_info)
                query_texts: list[str] = []
                if isinstance(queries, list):
                    query_texts.extend(str(q) for q in queries if q)
                for query_text in query_texts:
                    is_similar, similarity = self._check_query_similarity(query_text)
                    if (
                        is_similar
                        and web_search_count >= self.MIN_WEB_SEARCH_FOR_SIMILARITY_STOP
                    ):
                        return (
                            False,
                            f"⚠️ 当前查询与历史查询相似度很高（{similarity:.1%}）。如果之前的搜索结果已足够回答问题，请停止继续调用工具，并直接给出最终回答。",
                        )
            for call_info in get_in(
                [WEB_PAGES_EXTRACT_LLM], tool_arguments_by_name, []
            ):
                urls = get_in(["arguments", "urls"], call_info)
                url_texts: list[str] = []
                if isinstance(urls, list):
                    url_texts.extend(str(u) for u in urls if u)
                if url_texts:
                    overlap_ratio, extracted_count = self._check_url_overlap(url_texts)
                    if (
                        overlap_ratio > self.URL_OVERLAP_THRESHOLD
                        and web_pages_extract_count
                        >= self.MIN_WEB_PAGES_EXTRACT_FOR_OVERLAP_STOP
                    ):
                        return (
                            False,
                            f"⚠️ 当前 URL 列表中有 {extracted_count} 个 URL 已在之前提取过（重叠率 {overlap_ratio:.1%}）。如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
                        )
        if web_search_count >= self.MAX_WEB_SEARCH_COUNT:
            return (
                False,
                f"⚠️ 已执行 {web_search_count} 次搜索，结果可能已足够，直接回答。",
            )
        if web_pages_extract_count >= self.MAX_WEB_PAGES_EXTRACT_COUNT:
            return (
                False,
                f"⚠️ 已执行 {web_pages_extract_count} 次网页提取，内容可能已足够，直接回答。",
            )
        if len(self.extracted_urls) >= self.MAX_EXTRACTED_URLS:
            return (
                False,
                f"⚠️ 已提取 {len(self.extracted_urls)} 个 URL，内容可能已足够，直接回答。",
            )
        if total_tool_calls >= self.MAX_TOTAL_TOOL_CALLS:
            return (
                False,
                f"⚠️ 已执行 {total_tool_calls} 次工具调用，信息可能已足够，直接回答。",
            )
        return True, None

    @staticmethod
    def matches_tavily_tool(tool_name: str, bare_name: str) -> bool:
        return is_llm_tool(tool_name, TAVILY_SERVER, bare_name)

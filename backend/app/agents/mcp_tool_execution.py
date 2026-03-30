"""MCP 工具执行与迭代辅助（由原 MCPToolsAgent 抽取，供 ChatSessionAgent 组合使用）。"""

import asyncio
import json
from collections import defaultdict
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from toolz import get, get_in

from app.agents.utils import TavilyResultProcessor
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.prompts import (
    get_disabled_tools_message,
    get_gentle_tips_in_web_search,
    get_tool_call_sufficient_info_message,
)
from app.schemas.chat import SourceConfig
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.utils.common import normalize_url
from app.utils.context_compactor import ContextCompactor
from app.utils.logger import logger
from app.utils.mcp import count_tool_calls, has_tool_been_called
from app.utils.message import find_last_user_message
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator
from app.utils.vocab import VocabProcessor


def get_mcp_server_names(
    mcp_auto_mode: bool, source_config: SourceConfig
) -> list[str] | None:
    if mcp_auto_mode:
        return None
    return [key for key, value in source_config.model_dump().items() if value is True]


class MCPToolSession:
    """单次请求内的 MCP 工具状态与执行逻辑。"""

    WEB_SEARCH = "web_search"
    WEB_PAGES_EXTRACT = "web_pages_extract"
    TAVILY_TOOL_NAME = "tavily-mcp"
    QUERY_SIMILARITY_THRESHOLD = 0.7
    MAX_TOTAL_ITERATIONS = 10
    MAX_ITERATIONS_BY_TOOL = 5

    def __init__(
        self,
        mcp_manager: MCPClientManager,
        user_message: str,
        output_messages: list[ToolMessage],
    ):
        self.mcp_manager = mcp_manager
        self.current_user_message = user_message
        self.output_messages = output_messages
        self.tool_call_args_by_name: dict[str,
                                          list[dict[str, Any]]] = defaultdict(list)
        self.tool_result_compression = settings.chat_context.tool_result_compression
        self.compactor = ContextCompactor(
            embedding_model=settings.embedding_model,
            tool_result_compression_config=self.tool_result_compression,
        )
        self.token_calculator = TokenCalculator(
            settings.response_model.model_name)
        self.token_threshold: int = self.token_calculator.get_compression_threshold(
            0.5)
        self.extracted_urls: set[str] = set()
        self.vocab_processor = VocabProcessor()

    def reset_for_request(self, user_message: str) -> None:
        self.current_user_message = user_message
        self.extracted_urls = set()
        self.tool_call_args_by_name.clear()

    def _get_tools_state(
        self, tools: list[dict[str, Any]], iterations_by_tool: dict[str, int]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        available_tools: list[dict[str, Any]] = []
        disabled_tools: list[str] = []
        for tool in tools:
            tool_name = tool.get("function", {}).get("name", "")
            if iterations_by_tool.get(tool_name, 0) > 0:
                available_tools.append(tool)
            else:
                disabled_tools.append(tool_name)
        return available_tools, disabled_tools

    def _update_user_message_with_tool_hints(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        iterations_by_tool: dict[str, int],
        tool_call_user_message: str,
        iteration: int,
    ) -> None:
        _, disabled_tools = self._get_tools_state(
            tools, iterations_by_tool
        )
        suffix_user_message: list[str] = []
        if disabled_tools:
            logger.info(
                "Pre-filtered tools that reached max iterations",
                disabled_tools=disabled_tools,
                iteration=iteration + 1,
            )
            suffix_user_message.append(
                get_disabled_tools_message(disabled_tools))
        if has_tool_been_called([self.WEB_SEARCH], self.output_messages):
            suffix_user_message.append(get_gentle_tips_in_web_search())
        if has_tool_been_called([self.WEB_PAGES_EXTRACT], self.output_messages):
            if len(self.extracted_urls) >= 3:
                suffix_user_message.append(
                    f"⚠️ 已提取了 {len(self.extracted_urls)} 个 URL 的内容。如果这些内容已足够回答问题，请停止继续调用工具，并直接给出最终回答。"
                )
        should_continue, continue_message = self._should_continue_tool_calls(
            None)
        if not should_continue:
            if continue_message:
                suffix_user_message.append(continue_message)
            if iteration >= 1:
                suffix_user_message.append(
                    get_tool_call_sufficient_info_message())
        if suffix_user_message:
            last_user_message = find_last_user_message(messages)
            if last_user_message:
                hints_text = "\n".join(suffix_user_message)
                last_user_message["content"] = (
                    f"{tool_call_user_message}\n\n注意:\n{hints_text}"
                )
                logger.debug(
                    "Updated last user message",
                    last_user_message=last_user_message,
                )

    def _extract_tool_call_arguments(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall]
    ) -> dict[str, list[dict[str, Any]]]:
        tool_arguments: dict[str, list[dict[str, Any]]] = {}
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
                if tool_name not in tool_arguments:
                    tool_arguments[tool_name] = []
                tool_arguments[tool_name].append(
                    {
                        "arguments": arguments,
                        "tool_call_id": tool_call.id,
                    }
                )
            except (json.JSONDecodeError, Exception):
                continue
        return tool_arguments

    def _get_web_search_queries(self) -> list[str]:
        queries = []
        for call_info in self.tool_call_args_by_name.get(self.WEB_SEARCH, []):
            if query := get_in(["arguments", "query"], call_info):
                queries.append(query)
        return queries

    def _check_query_similarity(self, new_query: str) -> tuple[bool, float]:
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
        if not urls:
            return 0.0, 0
        normalized_urls = {normalize_url(url) for url in urls if url}
        extracted_count = len(normalized_urls & self.extracted_urls)
        overlap_ratio = (
            extracted_count / len(normalized_urls) if normalized_urls else 0.0
        )
        return overlap_ratio, extracted_count

    def _should_continue_tool_calls(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall] | None
    ) -> tuple[bool, str | None]:
        web_search_count = len(self._get_web_search_queries())
        web_pages_extract_count = len(
            self.tool_call_args_by_name.get(self.WEB_PAGES_EXTRACT, [])
        )
        total_tool_calls = count_tool_calls(self.output_messages)
        if tool_calls:
            tool_arguments = self._extract_tool_call_arguments(tool_calls)
            for call_info in get_in([self.WEB_SEARCH], tool_arguments, []):
                query = get_in(["arguments", "query"], call_info)
                if query:
                    is_similar, similarity = self._check_query_similarity(
                        query)
                    if is_similar and web_search_count >= 1:
                        return (
                            False,
                            f"⚠️ 当前查询与历史查询相似度很高（{similarity:.1%}）。如果之前的搜索结果已足够回答问题，请停止继续调用工具，并直接给出最终回答。",
                        )
            for call_info in get_in([self.WEB_PAGES_EXTRACT], tool_arguments, []):
                urls = get_in(["arguments", "urls"], call_info)
                if urls:
                    overlap_ratio, extracted_count = self._check_url_overlap(
                        urls)
                    if overlap_ratio > 0.7 and web_pages_extract_count >= 1:
                        return (
                            False,
                            f"⚠️ 当前 URL 列表中有 {extracted_count} 个 URL 已在之前提取过（重叠率 {overlap_ratio:.1%}）。如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
                        )
        if web_search_count >= 2:
            return (
                False,
                "⚠️ 已执行了 2 次 web_search。对于简单问题，通常一次搜索已足够。如果搜索结果已足够回答问题，请停止继续调用工具，并直接给出最终回答。",
            )
        if web_pages_extract_count >= 2:
            return (
                False,
                "⚠️ 已执行了 2 次 web_pages_extract。如果已提取的内容已足够回答问题，请停止继续调用工具，并直接给出最终回答。",
            )
        if len(self.extracted_urls) >= 5:
            return (
                False,
                f"⚠️ 已提取了 {len(self.extracted_urls)} 个 URL 的内容。如果这些内容已足够回答问题，请停止继续调用工具，并直接给出最终回答。",
            )
        if total_tool_calls >= 6:
            return (
                False,
                f"⚠️ 已执行了 {total_tool_calls} 次工具调用。如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
            )
        return True, None

    async def _execute_single_tool(
        self,
        tool_call: ChatCompletionMessageFunctionToolCall,
        current_iteration: int,
        iterations_by_tool: dict[str, int],
    ) -> ToolResultMessage:
        tool_name = tool_call.function.name
        start_time = get_current_time()
        if tool_name not in iterations_by_tool:
            logger.warning(
                "Tool not found in iterations tracking (unexpected), initializing as exhausted",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            iterations_by_tool[tool_name] = 0
        if iterations_by_tool[tool_name] <= 0:
            logger.info(
                "Tool max iterations reached, skipping",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            return ToolResultMessage(
                role="tool",
                is_error=True,
                tool_call_id=tool_call.id,
                content=f"Tool {tool_name} has hit max iterations, skipping",
            )
        iterations_by_tool[tool_name] -= 1
        try:
            arguments = json.loads(tool_call.function.arguments)
            if tool_name == self.WEB_PAGES_EXTRACT and (urls := get("urls", arguments)):
                normalized_urls = {normalize_url(url) for url in urls if url}
                new_urls = normalized_urls - self.extracted_urls
                if not new_urls:
                    logger.info(
                        "All URLs already extracted, skipping web_pages_extract",
                        urls=urls,
                        iteration=current_iteration + 1,
                    )
                    return ToolResultMessage(
                        role="tool",
                        is_error=False,
                        tool_call_id=tool_call.id,
                        content="⚠️ 提示：这些 URL 已经在之前的调用中提取过了。请检查历史工具调用结果，如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
                    )
                self.extracted_urls.update(new_urls)
                arguments["urls"] = new_urls
                logger.info(
                    "Filtered URLs for web_pages_extract",
                    original_count=len(urls),
                    new_count=len(new_urls),
                    iteration=current_iteration + 1,
                )
            self.tool_call_args_by_name[tool_name].append(
                {
                    "arguments": arguments,
                    "tool_call_id": tool_call.id,
                }
            )
            logger.info(
                "Calling MCP tool",
                tool_name=tool_name,
                tool_call_id=tool_call.id,
                iteration=current_iteration + 1,
                arguments=arguments,
            )
            result, filtered_params = await self.mcp_manager.call_tool(
                tool_name, arguments
            )
            content = self.mcp_manager.format_mcp_result(result)
            tool_call_result_message = ToolResultMessage(
                role="tool",
                content=content,
                is_error=len(content or "") == 0,
                tool_call_id=tool_call.id,
            )
            server_name = self.mcp_manager.get_server_for_tool(tool_name)
            if (
                server_name == self.TAVILY_TOOL_NAME
                and result.structured_content is not None
            ):
                tool_call_result_message = await self._apply_tavily_compaction(
                    tool_name=tool_name,
                    structured_content=result.structured_content,
                    tool_call_result_message=tool_call_result_message,
                )
            else:
                tool_call_result_message = await self._compact_tool_result_if_needed(
                    tool_call_result_message
                )
            content = tool_call_result_message.content or ""
            if filtered_params:
                warning_msg = (
                    f"⚠️ 警告：以下参数被忽略（工具 {tool_name} 不支持这些参数）："
                    f"{', '.join(filtered_params)}。"
                    f"请勿在后续调用中使用这些参数。\n\n"
                )
                content = warning_msg + content
                tool_call_result_message.content = content
                logger.info(
                    "Added filtered params warning to tool result",
                    tool_name=tool_name,
                    filtered_params=filtered_params,
                )
            logger.info(
                "MCP tool result received",
                tool_name=tool_name,
                tool_call_id=tool_call.id,
                duration=get_time_duration(start_time),
                content_length=len(content) if content else 0,
                content=content[:200] + "..." + content[-200:]
                if len(content) > 400
                else content,
            )
            return tool_call_result_message
        except Exception as e:
            tool_call_result_message = ToolResultMessage(
                role="tool",
                is_error=True,
                content=str(e),
                tool_call_id=tool_call.id,
            )
            logger.error(
                "Failed to call tool",
                error=e,
                tool_name=tool_name,
                iteration=current_iteration + 1,
                tool_call_id=tool_call.id,
                duration=get_time_duration(start_time),
                content_length=len(str(e)) if str(e) else 0,
            )
            return tool_call_result_message

    async def _apply_tavily_compaction(
        self,
        tool_name: str,
        structured_content: dict[str, Any],
        tool_call_result_message: ToolResultMessage,
    ) -> ToolResultMessage:
        processor = TavilyResultProcessor(
            compactor=self.compactor,
            user_query=self.current_user_message,
            tolerance_tokens_count=self.tool_result_compression.tolerance_tokens,
            threshold_tokens_count=self.tool_result_compression.threshold_tokens,
        )
        compaction = await processor.format_result(tool_name, structured_content)
        return tool_call_result_message.model_copy(
            update=compaction.model_dump(mode="json")
        )

    async def _compact_tool_result_if_needed(
        self, tool_message: ToolResultMessage
    ) -> ToolResultMessage:
        content = tool_message.content or ""
        if not content:
            return tool_message
        compaction = await self.compactor.compact_markdown_tool_result(
            query=self.current_user_message,
            content=content,
            tolerance_tokens_count=self.tool_result_compression.tolerance_tokens,
            threshold_tokens_count=self.tool_result_compression.threshold_tokens,
        )
        return tool_message.model_copy(update=compaction.model_dump(mode="json"))

    async def _execute_tool_calls_parallel(
        self,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        current_iteration: int,
        iterations_by_tool: dict[str, int],
    ) -> list[ToolResultMessage]:
        tasks = [
            self._execute_single_tool(
                tool_call, current_iteration, iterations_by_tool)
            for tool_call in tool_calls
            if tool_call is not None
        ]
        tool_results = await asyncio.gather(*tasks)
        return tool_results

    def build_tool_use_message(
        self,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        content: str,
        reasoning_content: str | None,
    ) -> ToolUseMessage:
        return ToolUseMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content or None,
        )

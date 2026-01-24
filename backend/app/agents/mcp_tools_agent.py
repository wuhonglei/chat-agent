"""MCP Tools Agent for handling MCP tool calls"""

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)
from toolz import get, get_in

from app.agents.base import BaseAgent
from app.agents.utils import TavilyResultProcessor
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.prompts import (
    get_disabled_tools_message,
    get_gentle_tips_in_web_search,
    get_prompt_with_mcp_servers,
    get_tool_call_sufficient_info_message,
)
from app.schemas.chat import ChatMessageItem, ChatRequest
from app.schemas.config import LLMConfig
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.schemas.token_stats import MCPToolsTokenStats
from app.utils.common import normalize_url
from app.utils.context_compactor import ContextCompactor
from app.utils.logger import logger
from app.utils.mcp import (
    count_tool_calls,
    extract_tool_call_names,
    has_tool_been_called,
)
from app.utils.message import (
    find_last_user_message,
    format_tool_call_messages_for_llm,
)
from app.utils.time import get_current_time, get_time_duration
from app.utils.vocab import VocabProcessor


class MCPToolsAgent(BaseAgent):
    """MCP工具调用Agent - 负责处理MCP工具调用逻辑"""

    # 工具名称常量
    WEB_SEARCH = "web_search"
    WEB_PAGES_EXTRACT = "web_pages_extract"
    TAVILY_TOOL_NAME = "tavily-mcp"

    # 相似度阈值
    QUERY_SIMILARITY_THRESHOLD = 0.7

    # 迭代次数限制
    MAX_TOTAL_ITERATIONS = 10  # Prevent infinite loops
    MAX_ITERATIONS_BY_TOOL = 5

    def __init__(
        self, think_mode: bool, llm_config: LLMConfig, mcp_manager: MCPClientManager
    ):
        super().__init__(think_mode, llm_config)
        self.mcp_manager = mcp_manager
        self.output_messages: list[ToolCallMessage] = []
        self.tool_call_args_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.duration: float | None = None
        self.token_stats: MCPToolsTokenStats | None = None
        self.compression_config = settings.compression
        self.compactor = ContextCompactor(
            embedding_model=settings.embedding_model,
            compression_config=settings.compression,
        )
        self.current_user_message: str = ""
        self.token_threshold: int = self.token_calculator.get_compression_threshold(0.5)
        # 跟踪已提取的 URL
        self.extracted_urls: set[str] = set()
        # 词汇处理器
        self.vocab_processor = VocabProcessor()

    def get_server_names(
        self, mcp_auto_mode: bool, source_config: dict
    ) -> list[str] | None:
        """获取MCP工具服务器名称"""
        if mcp_auto_mode:
            return None

        return [
            key for key, value in source_config.model_dump().items() if value is True
        ]

    async def stream_execute(
        self,
        chat_request: ChatRequest,
        history_messages: list[ChatMessageItem],
        client_ip: str | None,
    ) -> AsyncGenerator[str, None]:
        """
        流式执行MCP工具调用并返回SSE消息

        Args:
            chat_request: 聊天请求
            history_messages: 对话历史消息列表
            client_ip: 客户端IP

        Yields:
            str: SSE格式的消息
        """
        mcp_auto_mode = chat_request.mcp_auto_mode
        source_config = chat_request.source_config
        self.think_mode = chat_request.think_mode
        user_message = chat_request.content
        self.current_user_message = user_message

        # 重置跟踪属性
        self.extracted_urls = set()
        self.tool_call_args_by_name.clear()

        # 获取MCP工具
        server_names = self.get_server_names(mcp_auto_mode, source_config)
        tools = await self.mcp_manager.get_tools_for_llm(server_names, client_ip)

        if not tools:
            return

        # 准备消息
        system_prompt, tool_call_user_message = get_prompt_with_mcp_servers(
            user_message, mcp_auto_mode, server_names, client_ip
        )
        input_messages = self._compose_messages(
            system_prompt, history_messages, tool_call_user_message, []
        )

        # 流式调用LLM并收集工具调用消息
        start_time = get_current_time()
        async for message in self._call_llm_with_mcp_tools(
            input_messages,
            self.model_name,
            self.extra_body,
            tools,
            tool_call_user_message,
        ):
            if message:
                yield self.format_sse_message("mcp_tool_call", message.model_dump())

        if self.output_messages:
            self.duration = get_time_duration(start_time)
            # 创建 token 统计对象（内部进行所有 token 计算）
            self.token_stats = self.create_token_stats(
                input_messages=input_messages,
                tools=tools,
                output_messages=self.output_messages,
            )

            yield self.format_sse_message(
                "mcp_tool_call",
                {
                    "status": "done",
                    "duration": self.duration,
                    "token_stats": self.token_stats.model_dump(mode="json"),
                },
            )

    def _get_tools_state(
        self, tools: list[dict], iterations_by_tool: dict[str, int]
    ) -> tuple[list[dict], list[str]]:
        """Get the description of the tools"""
        available_tools: list[dict] = []
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
        messages: list[dict],
        tools: list[dict],
        iterations_by_tool: dict[str, int],
        tool_call_user_message: str,
        iteration: int,
    ) -> tuple[list[dict], list[str]]:
        """
        更新用户消息，添加工具调用相关的提示信息

        Args:
            messages: 消息列表
            tools: 工具列表
            iterations_by_tool: 每个工具的剩余迭代次数
            tool_call_user_message: 工具调用的用户消息
            iteration: 当前迭代次数

        Returns:
            tuple[list[dict], list[str]]: (可用工具列表, 禁用工具列表)
        """
        # 获取可用工具和禁用工具
        available_tools, disabled_tools = self._get_tools_state(
            tools, iterations_by_tool
        )

        # 构建后缀用户消息列表
        suffix_user_message: list[str] = []

        # 添加禁用工具提示
        if disabled_tools:
            logger.info(
                "Pre-filtered tools that reached max iterations",
                disabled_tools=disabled_tools,
                iteration=iteration + 1,
            )
            suffix_user_message.append(get_disabled_tools_message(disabled_tools))

        # 增强 web_search 检查
        if has_tool_been_called([self.WEB_SEARCH], self.output_messages):
            suffix_user_message.append(get_gentle_tips_in_web_search())

        # 增强 web_pages_extract 检查
        if has_tool_been_called([self.WEB_PAGES_EXTRACT], self.output_messages):
            if len(self.extracted_urls) >= 3:
                suffix_user_message.append(
                    f"⚠️ 已提取了 {len(self.extracted_urls)} 个 URL 的内容。如果这些内容已足够回答问题，请回复 'finish'。"
                )

        # 检查是否应该继续调用工具（在 LLM 调用前）
        should_continue, continue_message = self._should_continue_tool_calls(None)
        if not should_continue:
            if continue_message:
                suffix_user_message.append(continue_message)
            # 如果评估为不应该继续，添加通用提示
            if iteration >= 1:  # 至少执行了一次迭代
                suffix_user_message.append(get_tool_call_sufficient_info_message())

        # 如果有后缀消息，更新最后一条用户消息
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

        return available_tools, disabled_tools

    def _extract_tool_call_arguments(
        self, tool_calls: list[ChatCompletionMessageFunctionToolCall]
    ) -> dict[str, list[dict[str, Any]]]:
        """从工具调用中提取参数"""
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
        """
        从 tool_call_args_by_name 中提取所有 web_search 查询

        Returns:
            list[str]: web_search 查询列表
        """
        queries = []
        for call_info in self.tool_call_args_by_name.get(self.WEB_SEARCH, []):
            if query := get_in(["arguments", "query"], call_info):
                queries.append(query)
        return queries

    def _check_query_similarity(self, new_query: str) -> tuple[bool, float]:
        """
        检查新查询与历史查询的相似度

        Returns:
            tuple[bool, float]: (是否相似, 最高相似度)
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

        # 如果相似度 > 阈值，认为查询相似
        is_similar = max_similarity > self.QUERY_SIMILARITY_THRESHOLD
        return is_similar, max_similarity

    def _check_url_overlap(self, urls: list[str]) -> tuple[float, int]:
        """
        检查 URL 列表与已提取 URL 的重叠度

        Returns:
            tuple[float, int]: (重叠率, 已提取数量)
        """
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
        """
        评估是否应该继续调用工具

        Args:
            tool_calls: 当前迭代的工具调用列表（如果为 None，表示 LLM 还未决定）

        Returns:
            tuple[bool, str | None]: (是否应该继续, 提示消息)
        """
        # 统计工具调用次数
        web_search_count = len(self._get_web_search_queries())  # 已执行的搜索次数
        web_pages_extract_count = len(
            self.tool_call_args_by_name.get(self.WEB_PAGES_EXTRACT, [])
        )
        total_tool_calls = count_tool_calls(self.output_messages)

        # 检查当前工具调用（如果已确定）
        if tool_calls:
            tool_arguments = self._extract_tool_call_arguments(tool_calls)

            # 检查 web_search 查询相似度
            for call_info in get_in([self.WEB_SEARCH], tool_arguments, []):
                query = get_in(["arguments", "query"], call_info)
                if query:
                    is_similar, similarity = self._check_query_similarity(query)
                    if is_similar and web_search_count >= 1:
                        return (
                            False,
                            f"⚠️ 当前查询与历史查询相似度很高（{similarity:.1%}）。如果之前的搜索结果已足够回答问题，请回复 'finish'。",
                        )

            # 检查 web_pages_extract URL 重叠
            for call_info in get_in([self.WEB_PAGES_EXTRACT], tool_arguments, []):
                urls = get_in(["arguments", "urls"], call_info)
                if urls:
                    overlap_ratio, extracted_count = self._check_url_overlap(urls)
                    if overlap_ratio > 0.7 and web_pages_extract_count >= 1:
                        return (
                            False,
                            f"⚠️ 当前 URL 列表中有 {extracted_count} 个 URL 已在之前提取过（重叠率 {overlap_ratio:.1%}）。如果已获得足够信息，请回复 'finish'。",
                        )

        # 基于调用次数的检查
        if web_search_count >= 2:
            return (
                False,
                "⚠️ 已执行了 2 次 web_search。对于简单问题，通常一次搜索已足够。如果搜索结果已足够回答问题，请回复 'finish'。",
            )

        if web_pages_extract_count >= 2:
            return (
                False,
                "⚠️ 已执行了 2 次 web_pages_extract。如果已提取的内容已足够回答问题，请回复 'finish'。",
            )

        if len(self.extracted_urls) >= 5:
            return (
                False,
                f"⚠️ 已提取了 {len(self.extracted_urls)} 个 URL 的内容。如果这些内容已足够回答问题，请回复 'finish'。",
            )

        if total_tool_calls >= 6:
            return (
                False,
                f"⚠️ 已执行了 {total_tool_calls} 次工具调用。如果已获得足够信息，请回复 'finish'。",
            )

        return True, None

    async def _execute_single_tool(
        self,
        tool_call: ChatCompletionMessageFunctionToolCall,
        current_iteration: int,
        iterations_by_tool: dict[str, int],
    ) -> ToolCallResultMessage:
        """Execute a single tool call and return the result message"""
        tool_name = tool_call.function.name
        start_time = get_current_time()

        # 正常情况下，所有工具都应该在 iterations_by_tool 中（初始化时同步）
        # 如果不在，说明有异常，使用 get 方法安全获取，默认值为 0（视为已用完）
        if tool_name not in iterations_by_tool:
            logger.warning(
                "Tool not found in iterations tracking (unexpected), initializing as exhausted",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            iterations_by_tool[tool_name] = 0

        # Check if tool has reached max iterations BEFORE calling
        if iterations_by_tool[tool_name] <= 0:
            logger.info(
                "Tool max iterations reached, skipping",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            # Note: Tool should have been filtered out before LLM call, this is defensive check
            return ToolCallResultMessage(
                **{
                    "role": "tool",
                    "is_error": True,
                    "tool_call_id": tool_call.id,
                    "duration": get_time_duration(start_time),
                    "content": f"Tool {tool_name} has hit max iterations, skipping",
                }
            )

        # Decrement AFTER checking
        iterations_by_tool[tool_name] -= 1

        try:
            # Call the tool via MCP manager
            # Parse arguments
            arguments = json.loads(tool_call.function.arguments)

            # URL 去重处理（针对 web_pages_extract）
            if tool_name == self.WEB_PAGES_EXTRACT and (urls := get("urls", arguments)):
                # 规范化 URL（去除锚点）
                normalized_urls = {normalize_url(url) for url in urls if url}
                # 过滤掉已提取的 URL
                new_urls = normalized_urls - self.extracted_urls
                if not new_urls:
                    # 所有 URL 都已提取过
                    logger.info(
                        "All URLs already extracted, skipping web_pages_extract",
                        urls=urls,
                        iteration=current_iteration + 1,
                    )
                    return ToolCallResultMessage(
                        **{
                            "role": "tool",
                            "is_error": False,
                            "tool_call_id": tool_call.id,
                            "duration": get_time_duration(start_time),
                            "content": "⚠️ 提示：这些 URL 已经在之前的调用中提取过了。请检查历史工具调用结果，如果已获得足够信息，请回复 'finish'。",
                        }
                    )
                # 更新已提取的 URL 集合
                self.extracted_urls.update(new_urls)
                # 更新参数，只提取新的 URL
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
            # Add tool result to messages
            tool_call_result_message = ToolCallResultMessage(
                **{
                    "role": "tool",
                    "content": content,
                    "is_error": len(content or "") == 0,
                    "tool_call_id": tool_call.id,
                    "duration": get_time_duration(start_time),
                }
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

            # 如果有参数被过滤，在返回内容前添加警告信息，告知 LLM
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
                duration=tool_call_result_message.duration,
                content_length=len(content) if content else 0,
                content=content[:200] + "..." + content[-200:]
                if len(content) > 400
                else content,
            )
            return tool_call_result_message
        except Exception as e:
            tool_call_result_message = ToolCallResultMessage(
                **{
                    "role": "tool",
                    "is_error": True,
                    "content": str(e),
                    "tool_call_id": tool_call.id,
                    "duration": get_time_duration(start_time),
                }
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
        tool_call_result_message: ToolCallResultMessage,
    ) -> ToolCallResultMessage:
        processor = TavilyResultProcessor(
            compactor=self.compactor,
            user_query=self.current_user_message,
            tolerance_tokens_count=self.compression_config.tool_result_tolerance_tokens,
            threshold_tokens_count=self.compression_config.tool_result_threshold_tokens,
        )
        compaction = await processor.format_result(tool_name, structured_content)
        return tool_call_result_message.model_copy(
            update=compaction.model_dump(mode="json")
        )

    async def _compact_tool_result_if_needed(
        self, tool_message: ToolCallResultMessage
    ) -> ToolCallResultMessage:
        content = tool_message.content or ""
        if not content:
            return tool_message

        compaction = await self.compactor.compact_markdown_tool_result(
            query=self.current_user_message,
            content=content,
            tolerance_tokens_count=self.compression_config.tool_result_tolerance_tokens,
            threshold_tokens_count=self.compression_config.tool_result_threshold_tokens,
        )

        return tool_message.model_copy(update=compaction.model_dump(mode="json"))

    async def _execute_tool_calls_parallel(
        self,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        current_iteration: int,
        iterations_by_tool: dict[str, int],
    ) -> list[ToolCallResultMessage]:
        """Execute multiple tool calls in parallel and return the results

        Args:
            tool_calls: List of tool calls to execute
            current_iteration: Current iteration number
            iterations_by_tool: Dictionary tracking remaining iterations for each tool

        Returns:
            List of tool call result messages
        """
        # Create tasks for all tool calls
        tasks = [
            self._execute_single_tool(tool_call, current_iteration, iterations_by_tool)
            for tool_call in tool_calls
            if tool_call is not None
        ]
        # Execute all tasks in parallel
        tool_results = await asyncio.gather(*tasks)
        return tool_results

    async def _call_llm_with_mcp_tools(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
        tools: list[dict],
        tool_call_user_message: str,
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with MCP tools and handle tool calls, streaming results

        Args:
            messages: 消息列表
            model: 模型名称
            extra_body: 额外参数
            tools: 工具列表
            tool_call_user_message: 工具调用用户消息
        Yields:
            ToolCallMessage: Tool call related messages
        """
        logger.info(
            "MCP tool calls",
            model=model,
            tools_count=len(tools),
            messages_count=len(messages),
            extra_body=extra_body,
        )
        # 复制列表以避免修改原始参数（后续会修改 tools 列表）
        tools = list(tools) if tools else []
        iterations_by_tool = {
            tool["function"]["name"]: self.MAX_ITERATIONS_BY_TOOL for tool in tools
        }

        for iteration in range(self.MAX_TOTAL_ITERATIONS):
            logger.info(
                "Tool call iteration started",
                iteration=iteration + 1,
                max_iterations=self.MAX_TOTAL_ITERATIONS,
            )

            # 更新用户消息，添加工具调用相关的提示信息
            available_tools, _ = self._update_user_message_with_tool_hints(
                messages=messages,
                tools=tools,
                iterations_by_tool=iterations_by_tool,
                tool_call_user_message=tool_call_user_message,
                iteration=iteration,
            )

            # Call LLM with tools
            # 格式化 collected_messages，过滤掉额外的字段（如 token_count, duration, is_error）
            formatted_collected_messages = format_tool_call_messages_for_llm(
                self.output_messages, clear_reasoning_content=False
            )
            response = await self._call_llm_api(
                model=model,
                messages=messages + formatted_collected_messages,
                tools=available_tools if available_tools else None,
                stream=False,
                parallel_tool_calls=True,  # 启用并行工具调用
                extra_body=extra_body,
            )
            openai_message: ChatCompletionMessage = response.choices[0].message

            # 检查工具调用是否应该继续（在工具调用确定后）
            if openai_message.tool_calls:
                should_continue, continue_message = self._should_continue_tool_calls(
                    openai_message.tool_calls
                )
                if not should_continue and continue_message:
                    # 如果评估为不应该继续，添加提示但允许执行（保守策略）
                    logger.info(
                        "Tool calls may not be necessary",
                        message=continue_message,
                        iteration=iteration + 1,
                    )
                    # 注意：这里不阻止工具调用，只是记录日志
                    # 实际的阻止逻辑在 _execute_single_tool 中的 URL 去重

            if not openai_message.tool_calls:
                logger.info(
                    "No tool calls needed",
                    has_content=bool(openai_message.content),
                    content_length=len(openai_message.content)
                    if openai_message.content
                    else 0,
                )
                yield None
                return

            # Handle tool calls
            content = openai_message.content or ""
            reasoning_content = getattr(openai_message, "reasoning_content", "")
            assistant_message = AssistantToolCallMessage(
                **{
                    "role": "assistant",
                    "content": content,
                    "tool_calls": openai_message.tool_calls,
                    "reasoning_content": reasoning_content,
                }
            )
            self.output_messages.append(assistant_message)
            yield assistant_message
            tool_count = len(assistant_message.tool_calls)
            logger.info(
                "Tool calls required",
                tool_count=tool_count,
                iteration=iteration + 1,
            )
            # 只在 debug 模式下记录详细消息内容
            logger.debug(
                "Assistant message details",
                assistant_message=assistant_message.model_dump(),
            )

            # Execute all tool calls in parallel
            logger.info(
                "Executing tool calls in parallel",
                tool_count=tool_count,
                iteration=iteration + 1,
            )
            tool_results = await self._execute_tool_calls_parallel(
                assistant_message.tool_calls, iteration, iterations_by_tool
            )

            # Yield results in original order and collect them
            for tool_call_result_message in tool_results:
                self.output_messages.append(tool_call_result_message)
                yield tool_call_result_message

        # If we hit max iterations, return error message
        logger.info(
            "Max iterations reached",
            max_iterations=self.MAX_TOTAL_ITERATIONS,
        )
        yield None
        return

    def create_token_stats(
        self,
        input_messages: list[dict],
        tools: list[dict],
        output_messages: list[ToolCallMessage],
    ) -> MCPToolsTokenStats:
        """创建 MCP 工具调用的 token 统计对象

        Args:
            messages: 消息列表（用于计算 prompt_tokens）
            tools: 工具定义列表（用于计算 tools_tokens）
            output_messages: 收集的工具调用消息列表（用于计算 completion_tokens）

        Returns:
            MCPToolsTokenStats: token 统计对象
        """
        # 计算输入 token（包括消息和工具定义）
        prompt_tokens = self.token_calculator.count_messages_tokens(
            input_messages
        )  # 系统提示词、历史消息、用户消息
        tool_definition_tokens = self.token_calculator.count_tokens(json.dumps(tools))
        total_prompt_tokens = prompt_tokens + tool_definition_tokens

        # 计算输出 token（助手消息 + 工具调用结果）
        completion_tokens = self.token_calculator.count_messages_tokens(output_messages)

        tool_call_names = extract_tool_call_names(output_messages)
        tool_call_count = count_tool_calls(output_messages)

        return MCPToolsTokenStats(
            agent_name="mcp_tools",
            model_name=self.model_name,
            think_mode=self.think_mode,
            model_limit=self.model_limit,
            token_usage=self._create_token_usage(
                total_prompt_tokens, completion_tokens
            ),
            tool_call_count=tool_call_count,
            tool_definition_tokens=tool_definition_tokens,
            tool_call_names=tool_call_names,
        )

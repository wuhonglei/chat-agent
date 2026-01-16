"""MCP Tools Agent for handling MCP tool calls"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)

from app.agents.base import BaseAgent
from app.core.config import settings

# Import compression config
from app.mcp.mcp_client import MCPClientManager
from app.prompts import (
    get_prompt_with_mcp_servers,
    get_user_message_with_disabled_tools,
)
from app.schemas.chat import ChatMessageItem, ChatRequest
from app.schemas.config import LLMConfig
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.schemas.token_stats import MCPToolsTokenStats
from app.utils.context_compactor import ContextCompactor
from app.utils.logger import logger
from app.utils.mcp import count_tool_calls, extract_tool_call_names
from app.utils.message import (
    find_last_user_message,
    format_tool_call_messages_for_llm,
)
from app.utils.time import get_current_time, get_time_duration


class MCPToolsAgent(BaseAgent):
    """MCP工具调用Agent - 负责处理MCP工具调用逻辑"""

    def __init__(
        self, think_mode: bool, llm_config: LLMConfig, mcp_manager: MCPClientManager
    ):
        super().__init__(think_mode, llm_config)
        self.mcp_manager = mcp_manager
        self.output_messages: list[ToolCallMessage] = []
        self.duration: float | None = None
        self.token_stats: MCPToolsTokenStats | None = None
        self.compactor = ContextCompactor(
            summarizer_model=settings.summarizer_model,
            compression_config=settings.compression,
        )
        self.current_user_message: str = ""

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
    ) -> tuple[list[dict], int]:
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

            # 如果有参数被过滤，在返回内容前添加警告信息，告知 LLM
            if filtered_params:
                warning_msg = (
                    f"⚠️ 警告：以下参数被忽略（工具 {tool_name} 不支持这些参数）："
                    f"{', '.join(filtered_params)}。"
                    f"请勿在后续调用中使用这些参数。\n\n"
                )
                content = warning_msg + content
                logger.info(
                    "Added filtered params warning to tool result",
                    tool_name=tool_name,
                    filtered_params=filtered_params,
                )

            # Add tool result to messages
            tool_call_result_message = ToolCallResultMessage(
                **{
                    "role": "tool",
                    "content": content,
                    "is_error": len(content or "") == 0,
                    "tool_call_id": tool_call.id,
                    "token_count": self.token_calculator.count_tokens(content),
                    "duration": get_time_duration(start_time),
                }
            )
            tool_call_result_message = await self._compact_tool_result_if_needed(
                tool_name, tool_call_result_message
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

    async def _compact_tool_result_if_needed(
        self, tool_name: str, tool_message: ToolCallResultMessage
    ) -> ToolCallResultMessage:
        content = tool_message.content or ""
        if not content:
            return tool_message

        compaction = await self.compactor.compact_markdown_tool_result(
            query=self.current_user_message,
            content=content,
        )

        updated_fields = {
            "content": compaction.content,
            "content_token_count": self.token_calculator.count_tokens(
                compaction.content
            ),
            "relevance_applied": compaction.relevance_applied,
            "summary_applied": compaction.summary_applied,
            "original_token_count": compaction.original_token_count,
            "relevant_token_count": compaction.relevant_token_count,
            "summary_token_count": compaction.summary_token_count,
            "threshold_token_count": compaction.threshold_token_count,
        }
        updated_message = tool_message.model_copy(update=updated_fields)

        if compaction.summary_applied:
            logger.info(
                "Tool result compacted",
                tool_name=tool_name,
                original_token_count=compaction.original_token_count,
                relevant_token_count=compaction.relevant_token_count,
                summary_token_count=compaction.summary_token_count,
                threshold_token_count=compaction.threshold_token_count,
            )
        elif (
            compaction.relevance_applied
            and compaction.original_token_count != compaction.relevant_token_count
        ):
            logger.info(
                "Tool result filtered by relevance",
                tool_name=tool_name,
                original_token_count=compaction.original_token_count,
                relevant_token_count=compaction.relevant_token_count,
                threshold_token_count=compaction.threshold_token_count,
            )

        return updated_message

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
        max_total_iterations = 10  # Prevent infinite loops
        max_iterations_by_tool = 5
        # 复制列表以避免修改原始参数（后续会修改 tools 列表）
        tools = list(tools) if tools else []
        iterations_by_tool = {
            tool["function"]["name"]: max_iterations_by_tool for tool in tools
        }

        for iteration in range(max_total_iterations):
            logger.info(
                "Tool call iteration started",
                iteration=iteration + 1,
                max_iterations=max_total_iterations,
            )

            # Filter out tools that have reached max iterations BEFORE calling LLM
            # This prevents LLM from seeing tools it cannot use
            available_tools, disabled_tools = self._get_tools_state(
                tools, iterations_by_tool
            )
            if disabled_tools:
                logger.info(
                    "Pre-filtered tools that reached max iterations",
                    disabled_tools=disabled_tools,
                    iteration=iteration + 1,
                )
                last_user_message = find_last_user_message(messages)
                if last_user_message:
                    last_user_message["content"] = get_user_message_with_disabled_tools(
                        tool_call_user_message, disabled_tools
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
            assistant_message = AssistantToolCallMessage(
                **{
                    "role": "assistant",
                    "content": openai_message.content,
                    "tool_calls": openai_message.tool_calls,
                    "reasoning_content": hasattr(openai_message, "reasoning_content")
                    and openai_message.reasoning_content
                    or None,
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
            max_iterations=max_total_iterations,
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

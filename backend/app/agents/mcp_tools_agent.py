"""MCP Tools Agent for handling MCP tool calls"""
import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Optional, cast

from openai.types.chat import ChatCompletionMessage

from app.schemas.chat import ChatMessageItemReq, ChatRequest
from app.schemas.config import LLMConfig
from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.schemas.token_stats import MCPToolsTokenStats
from app.utils.common import filter_dict
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator
from app.utils.mcp import extract_tool_names, count_tool_calls
from app.mcp.mcp_client import MCPClientManager
from app.prompts import get_prompt_with_mcp_servers
from app.agents.base import BaseAgent


class MCPToolsAgent(BaseAgent):
    """MCP工具调用Agent - 负责处理MCP工具调用逻辑"""

    def __init__(self, llm_config: LLMConfig, mcp_manager: MCPClientManager, think_mode: bool = False):
        super().__init__(llm_config, think_mode)
        self.mcp_manager = mcp_manager
        self.collected_messages: list[ToolCallMessage] = []
        self.duration: Optional[float] = None
        self.token_stats: Optional[MCPToolsTokenStats] = None

    def create_token_stats(
        self,
        messages: list[dict],
        tools: list[dict],
        collected_messages: list[ToolCallMessage],
    ) -> MCPToolsTokenStats:
        """创建 MCP 工具调用的 token 统计对象

        Args:
            messages: 消息列表（用于计算 prompt_tokens）
            tools: 工具定义列表（用于计算 tools_tokens）
            collected_messages: 收集的工具调用消息列表（用于计算 completion_tokens）

        Returns:
            MCPToolsTokenStats: token 统计对象
        """
        # 计算输入 token（包括消息和工具定义）
        prompt_tokens = self.token_calculator.count_messages_tokens(messages)
        tools_tokens = self.token_calculator.count_tokens(json.dumps(tools))
        total_prompt_tokens = prompt_tokens + tools_tokens

        # 计算输出 token（助手消息 + 工具调用结果）
        completion_tokens = self.token_calculator.count_messages_tokens(
            collected_messages)

        tool_names = extract_tool_names(collected_messages)
        tool_calls_count = count_tool_calls(collected_messages)

        return MCPToolsTokenStats(
            agent_name="mcp_tools_agent",
            model_name=self.model,
            token_usage=self._create_token_usage(
                total_prompt_tokens, completion_tokens),
            tool_calls_count=tool_calls_count,
            tool_names=tool_names,
        )

    async def stream_execute(
        self,
        chat_request: ChatRequest,
        history: list[ChatMessageItemReq],
        client_ip: str | None
    ) -> AsyncGenerator[str, None]:
        """
        流式执行MCP工具调用并返回SSE消息

        Args:
            chat_request: 聊天请求
            history: 对话历史
            client_ip: 客户端IP

        Yields:
            str: SSE格式的消息
        """
        mcp_auto_mode = chat_request.mcp_auto_mode
        source_config = chat_request.source_config
        self.think_mode = chat_request.think_mode
        user_message = chat_request.content

        # 获取MCP工具
        server_names = None if mcp_auto_mode else filter_dict(
            source_config.model_dump(), [True])
        tools = await self.mcp_manager.get_tools_for_llm(server_names, client_ip)

        if not tools:
            return

        # 准备消息
        system_prompt, tool_call_user_message = get_prompt_with_mcp_servers(
            user_message, mcp_auto_mode, server_names, client_ip)
        new_messages = self._compose_messages(
            system_prompt, history, tool_call_user_message)

        # 流式调用LLM并收集工具调用消息
        start_time = get_current_time()
        async for message in self._call_llm_with_mcp_tools(
            new_messages, self.model, self.extra_body, tools
        ):
            if message:
                yield self.format_sse_message('mcp_tool_call', message.model_dump())

        if self.collected_messages:
            self.duration = get_time_duration(start_time)
            # 创建 token 统计对象（内部进行所有 token 计算）
            self.token_stats = self.create_token_stats(
                messages=new_messages,
                tools=tools,
                collected_messages=self.collected_messages
            )

            yield self.format_sse_message('mcp_tool_call', {
                'status': 'done',
                'duration': self.duration,
            })

    async def _call_llm_with_mcp_tools(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
        tools: list[dict],
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with MCP tools and handle tool calls, streaming results

        Args:
            messages: 消息列表
            model: 模型名称
            extra_body: 额外参数
            tools: 工具列表

        Yields:
            ToolCallMessage: Tool call related messages
        """
        logger.info("MCP tool calls", model=model, tools_count=len(
            tools), messages_count=len(messages), extra_body=extra_body)
        max_total_iterations = 10  # Prevent infinite loops
        max_iterations_by_tool = 5
        # 复制列表以避免修改原始参数（后续会修改 tools 列表）
        tools = list(tools) if tools else []
        iterations_by_tool = {
            tool['function']['name']: max_iterations_by_tool for tool in tools}
        for iteration in range(max_total_iterations):
            logger.info("Tool call iteration started", iteration=iteration +
                        1, max_iterations=max_total_iterations)

            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                parallel_tool_calls=True,  # 启用并行工具调用
                messages=messages + self.collected_messages,
                tools=tools if tools else None,
                stream=False,
                extra_body=extra_body,
            )
            openai_message: ChatCompletionMessage = response.choices[0].message

            if not openai_message.tool_calls:
                logger.info(
                    "No tool calls needed",
                    has_content=bool(openai_message.content),
                    content_length=len(
                        openai_message.content) if openai_message.content else 0,
                )
                yield None
                return

            # Handle tool calls
            assistant_message = AssistantToolCallMessage(**{
                'role': 'assistant',
                'content': openai_message.content,
                'tool_calls': openai_message.tool_calls,
                'reasoning_content': hasattr(openai_message, 'reasoning_content') and openai_message.reasoning_content or None,
            })
            self.collected_messages.append(assistant_message)
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

            # Execute tool calls in parallel and stream results
            tools_to_remove = set()  # 收集需要移除的工具名称

            async def execute_single_tool(tool_call: Any) -> ToolCallResultMessage:
                """Execute a single tool call and return the result message"""
                tool_name = cast(str, tool_call.function.name)
                start_time = get_current_time()

                # 正常情况下，所有工具都应该在 iterations_by_tool 中（初始化时同步）
                # 如果不在，说明有异常，使用 get 方法安全获取，默认值为 0（视为已用完）
                if tool_name not in iterations_by_tool:
                    logger.warning(
                        "Tool not found in iterations tracking (unexpected), initializing as exhausted",
                        tool_name=tool_name,
                        iteration=iteration + 1,
                    )
                    iterations_by_tool[tool_name] = 0

                # Check if tool has reached max iterations BEFORE calling
                if iterations_by_tool[tool_name] <= 0:
                    logger.info(
                        "Tool max iterations reached, skipping",
                        tool_name=tool_name,
                        iteration=iteration + 1,
                    )
                    # 标记该工具需要从列表中移除
                    tools_to_remove.add(tool_name)
                    return ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                        "content": f'Tool {tool_name} has hit max iterations, skipping'
                    })

                # Decrement AFTER checking
                iterations_by_tool[tool_name] -= 1

                # 如果工具达到上限，标记需要移除
                if iterations_by_tool[tool_name] <= 0:
                    tools_to_remove.add(tool_name)

                try:
                    # Call the tool via MCP manager
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)
                    logger.info(
                        "Calling MCP tool",
                        tool_name=tool_name,
                        tool_call_id=tool_call.id,
                        iteration=iteration + 1,
                        arguments=arguments,
                    )
                    result, filtered_params = await self.mcp_manager.call_tool(tool_name, arguments)
                    content = self.mcp_manager.format_mcp_result(
                        result)

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
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "content": content,
                        "is_error": len(content or '') == 0,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    logger.info(
                        "MCP tool result received",
                        tool_name=tool_name,
                        tool_call_id=tool_call.id,
                        duration=tool_call_result_message.duration,
                        content_length=len(content) if content else 0,
                        content=content[:200] + '...' +
                        content[-200:] if len(content) > 400 else content,
                    )
                    return tool_call_result_message
                except Exception as e:
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": str(e),
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    logger.error(
                        "Failed to call tool",
                        error=e,
                        tool_name=tool_name,
                        iteration=iteration + 1,
                        tool_call_id=tool_call.id,
                        duration=get_time_duration(start_time),
                        content_length=len(str(e)) if str(e) else 0,
                    )
                    return tool_call_result_message

            # Execute all tool calls in parallel
            logger.info(
                "Executing tool calls in parallel",
                tool_count=tool_count,
                iteration=iteration + 1,
            )
            # Create tasks for all tool calls
            tasks = [execute_single_tool(
                tool_call) for tool_call in assistant_message.tool_calls]
            # Execute all tasks in parallel
            tool_results = await asyncio.gather(*tasks)

            # Remove tools that have reached max iterations from the tools list
            if tools_to_remove:
                original_count = len(tools)
                tools[:] = [
                    tool for tool in tools
                    if tool.get("function", {}).get("name") not in tools_to_remove
                ]
                # 注意：不从 iterations_by_tool 移除记录，保留用于防御性检查
                # 如果 LLM 错误地尝试调用已移除的工具，可以通过 iterations_by_tool[tool_name] <= 0 判断
                removed_count = original_count - len(tools)
                logger.info(
                    "Removed tools that reached max iterations",
                    removed_tools=list(tools_to_remove),
                    removed_count=removed_count,
                    remaining_tools=len(tools),
                    iteration=iteration + 1,
                )
                tools_to_remove.clear()  # 清空集合，为下次迭代准备

            # Yield results in original order and collect them
            for tool_call_result_message in tool_results:
                self.collected_messages.append(tool_call_result_message)
                yield tool_call_result_message

        # If we hit max iterations, return error message
        logger.info(
            "Max iterations reached",
            max_iterations=max_total_iterations,
        )
        yield None
        return

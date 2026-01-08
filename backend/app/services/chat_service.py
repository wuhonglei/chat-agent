"""Chat service for RAG-based Q&A"""
import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Optional, cast

from jsonschema import validate, ValidationError as JsonSchemaValidationError
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings
from app.schemas.chat import ChatMessageItemReq, ChatRequest, CollectedResponse, ComponentToolConfig, ComponentToolWhen
from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.utils.common import filter_dict
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.utils.message import clear_reasoning_content, format_message_for_llm, format_assistant_tool_call_message
from app.utils.model import get_model_extra_body
from app.mcp.mcp_client import MCPClientManager
from app.prompts import get_default_system_prompt, get_prompt_for_title, get_prompt_with_mcp_servers
from app.services.component_schema_service import ComponentSchemaService
from app.utils.component_tools import convert_schema_to_tool_definition
from app.prompts.prompt_utils import get_prompt_for_component_render_data, get_user_message_with_component_data
from pydantic import BaseModel


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.debug = settings.app.debug
        self.client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.api_base,
        )
        self.tool_model_config = settings.tool
        self.tool_client = AsyncOpenAI(
            api_key=settings.tool.api_key,
            base_url=settings.tool.api_base,
        )
        self.mcp_manager = mcp_manager
        self.collected_content = ''  # 收集的完整响应内容
        self.collected_reasoning = ''  # 收集的推理内容
        # 工具调用记录
        self.collected_mcp_tool_call_messages: list[ToolCallMessage] = []
        self.collected_component_tool_call_messages: list[ToolCallMessage] = []
        self.total_duration: Optional[float] = None  # 总耗时
        self.tool_calls_duration: Optional[float] = None  # 工具调用耗时
        self.component_tool_calls_duration: Optional[float] = None  # 组件工具调用耗时
        self.reasoning_duration: Optional[float] = None  # 推理耗时
        self.content_duration: Optional[float] = None  # 内容生成耗时
        self.schema_service = ComponentSchemaService(
            debug=self.debug)  # 复用 ComponentSchemaService 实例

    async def _stream_final_response(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream final response"""
        start_time = get_current_time()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            extra_body=extra_body,
        )
        logger.info("Using LLM model", model=model)
        reasoning_started = False
        content_started = False
        # 重命名变量，区分推理和内容的计时，避免混淆
        last_reasoning_time = start_time
        last_content_time = start_time

        async for chunk in response:
            # 安全检查：确保 choices 存在且不为空
            if not chunk.choices:
                continue

            delta = getattr(chunk.choices[0], 'delta', None)
            if not delta:
                continue

            # 处理 reasoning_content
            reasoning_content = getattr(delta, 'reasoning_content', None)
            content = getattr(delta, 'content', None)

            # 1. 优先处理推理内容（允许同时存在推理和内容的极端情况）
            if reasoning_content:
                # 如果之前在输出 content，先结束 content
                if content_started:
                    self.content_duration = get_time_duration(
                        last_content_time)
                    yield self.format_sse_message('content', {
                        'status': 'done',
                        'content': '',
                        'duration': self.content_duration,
                    })
                    content_started = False

                status = 'start' if not reasoning_started else 'continue'
                reasoning_started = True
                last_reasoning_time = get_current_time()
                yield self.format_sse_message('reasoning', {
                    'status': status,
                    'content': reasoning_content,
                })

            # 2. 处理 content（不再用 elif，避免推理内容覆盖内容的判断）
            if content:
                # 如果之前在输出 reasoning，先结束 reasoning
                if reasoning_started:
                    self.reasoning_duration = get_time_duration(
                        last_reasoning_time)
                    yield self.format_sse_message('reasoning', {
                        'status': 'done',
                        'duration': self.reasoning_duration,
                    })
                    reasoning_started = False

                status = 'start' if not content_started else 'continue'
                content_started = True
                last_content_time = get_current_time()
                yield self.format_sse_message('content', {
                    'status': status,
                    'content': content,
                })

        # 处理循环结束后的收尾逻辑（关键修复：分开判断，不再用 elif）
        # 1. 如果推理未结束，发送推理 done 状态
        if reasoning_started:
            self.reasoning_duration = get_time_duration(last_reasoning_time)
            yield self.format_sse_message('reasoning', {
                'status': 'done',
                'duration': self.reasoning_duration,
            })

        # 2. 如果内容未结束，发送内容 done 状态（独立判断，即使有推理也会处理）
        if content_started:
            self.content_duration = get_time_duration(last_content_time)
            yield self.format_sse_message('content', {
                'status': 'done',
                'content': '',
                'duration': self.content_duration,
            })

        # 3. 关键补充：处理「有推理但无内容」的边界情况
        if reasoning_started and not content_started and not content:
            # 发送一个空的 content done 状态，确保前端感知到内容结束
            yield self.format_sse_message('content', {
                'status': 'done',
                'content': '[模型已完成深入推理，详见思考过程]',
                'duration': 0.0,
            })

        logger.info("Stream final response completed",
                    duration=get_time_duration(start_time))

    async def _call_llm_with_mcp_tools(
        self,
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
        tools: list[dict],
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with MCP tools and handle tool calls, streaming results

        Yields:
            tuple[str, list]: First element is SSE message (or None), second is accumulated messages
        Returns:
            list[AssistantMessage]: Final tool call messages
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
            response = await self.tool_client.chat.completions.create(
                model=model,
                parallel_tool_calls=True,  # 启用并行工具调用
                messages=messages + self.collected_mcp_tool_call_messages,
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
            self.collected_mcp_tool_call_messages.append(assistant_message)
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
                self.collected_mcp_tool_call_messages.append(
                    tool_call_result_message)
                yield tool_call_result_message

        # If we hit max iterations, return error message
        logger.info(
            "Max iterations reached",
            max_iterations=max_total_iterations,
        )
        yield None
        return

    def _check_component_condition(
        self,
        component_config: ComponentToolConfig,
        mcp_tool_names: list[str],
        mcp_tool_call_contents: list[str],
        user_message: str,
    ) -> bool:
        """检查组件是否满足条件

        Args:
            component_config: 组件配置
            mcp_tool_names: 已调用的 MCP 工具名称列表
            mcp_tool_call_contents: MCP 工具响应内容列表
            user_message: 用户消息内容

        Returns:
            bool: 是否满足条件
        """
        when = component_config.when
        when_condition = component_config.when_condition

        # 收集所有条件的匹配结果
        condition_results = []

        # 检查 mcp_tool_names 条件
        if when.mcp_tool_names is not None:
            # 检查是否有任何已调用的工具名称部分包含匹配
            matched = any(
                any(expected_tool in actual_tool for actual_tool in mcp_tool_names)
                for expected_tool in when.mcp_tool_names
            )
            condition_results.append(matched)
            logger.debug(
                "Checking mcp_tool_names condition",
                component_name=component_config.name,
                expected_tools=when.mcp_tool_names,
                actual_tools=mcp_tool_names,
                matched=matched,
            )

        # 检查 mcp_tool_call_content 条件
        if when.mcp_tool_call_content is not None:
            # 检查是否有任何工具响应内容包含指定的字符串
            matched = any(
                any(keyword in content for content in mcp_tool_call_contents)
                for keyword in when.mcp_tool_call_content
            )
            condition_results.append(matched)
            logger.debug(
                "Checking mcp_tool_call_content condition",
                component_name=component_config.name,
                expected_keywords=when.mcp_tool_call_content,
                matched=matched,
            )

        # 检查 user_message 条件
        if when.user_message is not None:
            # 检查用户消息是否包含指定的字符串
            matched = when.user_message in user_message
            condition_results.append(matched)
            logger.debug(
                "Checking user_message condition",
                component_name=component_config.name,
                expected_keyword=when.user_message,
                matched=matched,
            )

        # 如果没有设置任何条件，默认返回 True（允许调用）
        if not condition_results:
            logger.debug(
                "No conditions set, allowing component",
                component_name=component_config.name,
            )
            return True

        # 根据 when_condition 决定组合逻辑
        if when_condition == "and":
            # 所有条件都必须满足
            result = all(condition_results)
        else:  # "or"
            # 至少一个条件满足即可
            result = any(condition_results)

        logger.info(
            "Component condition check result",
            component_name=component_config.name,
            when_condition=when_condition,
            condition_results=condition_results,
            result=result,
        )

        return result

    def _extract_mcp_tool_info(
        self,
        mcp_tool_call_messages: list[ToolCallMessage],
    ) -> tuple[list[str], list[str]]:
        """从 MCP 工具调用消息中提取工具名称和响应内容

        Args:
            mcp_tool_call_messages: MCP 工具调用消息列表

        Returns:
            tuple[list[str], list[str]]: (工具名称列表, 工具响应内容列表)
        """
        tool_names: list[str] = []
        tool_call_contents: list[str] = []

        for message in mcp_tool_call_messages:
            if isinstance(message, AssistantToolCallMessage) and message.tool_calls:
                # 从 assistant 消息中提取工具名称
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_names.append(tool_name)
            elif isinstance(message, ToolCallResultMessage) and not message.is_error:
                # 从 tool 消息中提取响应内容
                tool_call_contents.append(message.content)

        return tool_names, tool_call_contents

    async def _call_llm_with_component_tools(
        self,
        # system message + user_message + mcp tool messages
        messages: list[dict],
        model: str,
        extra_body: dict[str, Any],
        component_tool_names: list[str],
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with component tools and collect component data

        Args:
            messages: 包含 system message、user message 和 MCP tool call messages 的消息列表
            model: LLM 模型名称
            extra_body: 模型额外参数
            component_tool_names: 组件工具名称列表（例如：['weather']）

        Yields:
            ToolCallMessage: 工具调用相关的消息
        """
        if not component_tool_names:
            return

        # 获取并转换组件工具的 JSON schema 为 LLM tool 定义格式
        try:
            schemas = await self.schema_service.get_schemas(component_tool_names)
        except Exception as e:
            logger.error(
                "Failed to get component schemas",
                component_tool_names=component_tool_names,
                error=e,
            )
            return

        if not schemas:
            logger.warning(
                "No schemas retrieved",
                component_tool_names=component_tool_names,
            )
            return

        # 将 JSON schemas 转换为 LLM tool 定义
        component_tools = []
        for component_tool_name, json_schema in schemas.items():
            try:
                tool_definition = convert_schema_to_tool_definition(
                    component_tool_name, json_schema
                )
                component_tools.append(tool_definition)
                logger.info(
                    "Component tool definition created",
                    component_tool_name=component_tool_name,
                )
            except Exception as e:
                logger.error(
                    "Failed to convert schema to tool definition",
                    component_tool_name=component_tool_name,
                    error=e,
                )
                continue

        if not component_tools:
            logger.warning("No component tools created")
            return

        # 调用 LLM API，让 LLM 决定是否调用组件工具
        max_iterations = len(component_tools)  # 组件工具调用最多迭代次数

        for iteration in range(max_iterations):
            logger.info(
                "Component tool call iteration started",
                iteration=iteration + 1,
                max_iterations=max_iterations,
            )

            # 调用 LLM
            response = await self.tool_client.chat.completions.create(
                model=model,
                messages=messages + self.collected_component_tool_call_messages,
                tools=component_tools,
                stream=False,
                extra_body=extra_body,
            )
            openai_message: ChatCompletionMessage = response.choices[0].message

            if not openai_message.tool_calls:
                logger.info(
                    "No component tool calls needed",
                    has_content=bool(openai_message.content),
                )
                return

            # 处理组件工具调用
            assistant_message = AssistantToolCallMessage(**{
                'role': 'assistant',
                'content': openai_message.content,
                'tool_calls': openai_message.tool_calls,
                'reasoning_content': hasattr(openai_message, 'reasoning_content') and openai_message.reasoning_content or None,
            })
            self.collected_component_tool_call_messages.append(
                assistant_message)
            yield assistant_message

            tool_count = len(assistant_message.tool_calls)
            logger.info(
                "Component tool calls required",
                tool_count=tool_count,
                iteration=iteration + 1,
            )

            # 收集组件工具调用的结果
            for tool_call in assistant_message.tool_calls:
                tool_name = cast(str, tool_call.function.name)
                component_name_prefix = "generate_component_"
                # 提取组件名称（去掉 generate_component_ 前缀）
                component_tool_name = tool_name.replace(
                    component_name_prefix, "")
                if component_tool_name not in schemas:
                    logger.warning(
                        "Component schema not found",
                        tool_name=tool_name,
                        component_tool_name=component_tool_name,
                        tool_call_id=tool_call.id,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": f"Component schema not found for tool {tool_name}, skipping",
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_component_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message
                    continue

                # 解析工具调用的 arguments
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    schema = schemas[component_tool_name]
                    validate(instance=arguments, schema=schema)
                    logger.debug(
                        "Component tool call arguments validated",
                        tool_name=tool_name,
                        arguments=arguments,
                        tool_call_id=tool_call.id,
                    )
                    # 创建工具调用结果消息
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": False,
                        "content": "Component data generated successfully",
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_component_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message

                    # 从 component_tools 中移除已成功构造的组件
                    component_tools[:] = [
                        tool for tool in component_tools
                        if tool.get("function", {}).get("name") != tool_name
                    ]
                    logger.debug(
                        "Component tool removed from list",
                        tool_name=tool_name,
                        remaining_tools=len(component_tools),
                    )
                except JsonSchemaValidationError as e:
                    error_msg = f"JSON schema validation failed: {e.message}"
                    logger.warning(
                        "Component tool call arguments validation failed",
                        tool_name=tool_name,
                        component_tool_name=component_tool_name,
                        tool_call_id=tool_call.id,
                        validation_error=error_msg,
                        arguments=arguments,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": error_msg,
                        "tool_call_id": tool_call.id,
                        "duration": 0.0,
                    })
                    self.collected_component_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message
                    continue

        logger.info(
            "Component tool call iterations completed",
            max_iterations=max_iterations,
        )
        return

    def format_sse_message(self, msg_type: str, data=None) -> str:
        """Format SSE (Server-Sent Events) message"""
        if data is None:
            return f"data: {json.dumps({'type': msg_type, 'data': {}}, ensure_ascii=False)}\n\n"

        # 如果 data 是 BaseModel
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="json")
        if msg_type == 'content':
            self.collected_content += data.get('content') or ''
        elif msg_type == 'reasoning':
            self.collected_reasoning += data.get('content') or ''
        return f"data: {json.dumps({'type': msg_type, 'data': data}, ensure_ascii=False)}\n\n"

    async def stream_message(
        self,
        chat_request: ChatRequest,
        history: list[ChatMessageItemReq],
        client_ip: str | None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        try:
            # Choose between retrieval and MCP tool calling
            mcp_auto_mode = chat_request.mcp_auto_mode
            source_config = chat_request.source_config
            think_mode = chat_request.think_mode
            user_message = chat_request.content
            tool_model = self.tool_model_config.think_model if think_mode else self.tool_model_config.model
            extra_body = get_model_extra_body(think_mode)
            # Get MCP tools for LLM
            server_names = None if mcp_auto_mode else filter_dict(
                source_config.model_dump(), [True])
            tools = await self.mcp_manager.get_tools_for_llm(server_names, client_ip)
            if tools:
                # Call LLM with tools and stream results
                system_prompt, tool_call_user_message = get_prompt_with_mcp_servers(
                    user_message, mcp_auto_mode, server_names, client_ip)
                new_messages = self._compose_messages(
                    system_prompt, history, tool_call_user_message)

                # Stream tool calls and collect messages
                start_time = get_current_time()
                async for message in self._call_llm_with_mcp_tools(
                    new_messages, tool_model, extra_body, tools
                ):
                    # Update accumulated messages
                    if message:
                        yield self.format_sse_message('mcp_tool_call', message.model_dump())

                if self.collected_mcp_tool_call_messages:
                    self.tool_calls_duration = get_time_duration(start_time)
                    yield self.format_sse_message('mcp_tool_call', {
                        'status': 'done',
                        'duration': self.tool_calls_duration,
                    })

            # 在 MCP tools 调用完成后，调用组件工具
            component_tools_for_backend = chat_request.component_tools_for_backend
            if component_tools_for_backend:
                # 提取 MCP 工具信息
                mcp_tool_names, mcp_tool_call_contents = self._extract_mcp_tool_info(
                    self.collected_mcp_tool_call_messages
                )

                # 根据条件过滤组件工具
                filtered_component_tools = []
                for component_config in component_tools_for_backend:
                    if self._check_component_condition(
                        component_config,
                        mcp_tool_names,
                        mcp_tool_call_contents,
                        user_message,
                    ):
                        filtered_component_tools.append(component_config.name)
                        logger.info(
                            "Component tool condition satisfied",
                            component_name=component_config.name,
                        )
                    else:
                        logger.info(
                            "Component tool condition not satisfied, skipping",
                            component_name=component_config.name,
                        )

                if filtered_component_tools:
                    # 准备消息列表（包含 system message、user message 和 MCP tool messages）
                    system_prompt, component_user_message = get_prompt_for_component_render_data(
                        user_message)
                    component_messages = self._compose_messages(
                        system_prompt, [], component_user_message, self.collected_mcp_tool_call_messages
                    )

                    # 调用组件工具
                    start_time = get_current_time()
                    async for message in self._call_llm_with_component_tools(
                        component_messages, tool_model, extra_body, filtered_component_tools
                    ):
                        if message:
                            yield self.format_sse_message('component_tool_call', message.model_dump())

                    if self.collected_component_tool_call_messages:
                        self.component_tool_calls_duration = get_time_duration(
                            start_time)
                        yield self.format_sse_message('component_tool_call', {
                            'status': 'done',
                            'duration': self.component_tool_calls_duration,
                        })
                else:
                    logger.info(
                        "No component tools passed condition check",
                        total_components=len(component_tools_for_backend),
                    )

            # 将组件数据拼接到 user_message
            final_user_message = get_user_message_with_component_data(
                user_message, self.collected_component_tool_call_messages, self.schema_service.get_schema_cache()
            )

            system_prompt = get_default_system_prompt(include_date=False)
            # 将工具调用历史拼接到用户消息中
            new_messages = self._compose_messages(
                system_prompt, history, final_user_message, self.collected_mcp_tool_call_messages)
            final_model = settings.llm.think_model if think_mode else settings.llm.model
            async for chunk in self._stream_final_response(new_messages, final_model, extra_body):
                yield chunk
            return

        except Exception as e:
            logger.error("Failed to stream message", error=e)
            raise

    async def generate_title(self, user_message: str) -> str:
        """Generate title for the chat"""
        system_prompt, new_user_message = get_prompt_for_title(user_message)
        messages = self._compose_messages(
            system_prompt, [], new_user_message)
        title_response = await self.client.chat.completions.create(
            model=settings.llm.model,
            messages=messages,
            stream=False,
        )
        return title_response.choices[0].message.content

    def get_collected_response(self) -> CollectedResponse:
        """获取已收集的助手消息内容"""
        return CollectedResponse(
            content=self.collected_content,
            reasoning=self.collected_reasoning,
            tool_calls=[tool_call.model_dump(
            ) for tool_call in self.collected_mcp_tool_call_messages],
            component_tool_calls=[tool_call.model_dump(
            ) for tool_call in self.collected_component_tool_call_messages],
            tool_calls_duration=self.tool_calls_duration,
            component_tool_calls_duration=self.component_tool_calls_duration,
            reasoning_duration=self.reasoning_duration,
            content_duration=self.content_duration,
            total_duration=self.total_duration,
        )

    @staticmethod
    def _compose_messages(
        system_prompt: str,
        history: list[ChatMessageItemReq],
        user_message: str,
        tool_call_messages: Optional[list[ToolCallMessage]] = None,
    ) -> list[dict]:
        """Build prompt for LLM

        Args:
            system_prompt: System prompt message
            history: Conversation history
            user_message: Current user message
            tool_call_messages: Optional tool call messages (assistant tool calls and tool results)

        Returns:
            Message list with correct order: system_prompt -> history -> user_message -> tool_call_messages
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        history = history or []
        # 处理历史消息，确保包含 tool_calls 的 assistant 消息有 reasoning_content 字段
        for msg in history:
            msg_dict = format_message_for_llm(msg)
            msg_dict = clear_reasoning_content(msg_dict)
            messages.append(msg_dict)

        messages.append({"role": "user", "content": user_message})

        # 如果有 tool_call_messages，转换为字典格式并追加
        if not tool_call_messages:
            return messages

        # 第一步：收集所有有效的 tool_call_id（从成功的 ToolCallResultMessage）
        valid_tool_call_ids = set()
        for message in tool_call_messages:
            if isinstance(message, ToolCallResultMessage):
                if not message.is_error:
                    valid_tool_call_ids.add(message.tool_call_id)

        # 第二步：收集 assistant 消息中实际存在的 tool_call_id（只保留那些有成功结果的）
        # 这样可以确保 tool 消息和 assistant 消息成对出现
        assistant_tool_call_ids = set()
        for message in tool_call_messages:
            if isinstance(message, AssistantToolCallMessage):
                for tool_call in (message.tool_calls or []):
                    if tool_call.id in valid_tool_call_ids:
                        assistant_tool_call_ids.add(tool_call.id)

        # 第三步：只保留正确的工具调用（ToolCallResultMessage is_error=False 且有对应的 assistant 消息）
        filtered_tool_call_messages = []
        for message in tool_call_messages:
            if isinstance(message, AssistantToolCallMessage):
                # 保留 assistant 工具调用中有效的工具调用
                # 使用 model_copy() 创建副本，避免修改原始对象
                filtered_tool_calls = [
                    tool_call for tool_call in (message.tool_calls or [])
                    if tool_call.id in assistant_tool_call_ids
                ]
                if filtered_tool_calls:
                    # 创建新对象副本，只更新 tool_calls 字段
                    filtered_message = message.model_copy(
                        update={"tool_calls": filtered_tool_calls})
                    filtered_tool_call_messages.append(filtered_message)
            elif isinstance(message, ToolCallResultMessage):
                # 只保留没有错误且有对应 assistant 消息的工具调用结果
                if not message.is_error and message.tool_call_id in assistant_tool_call_ids:
                    filtered_tool_call_messages.append(message)

        # 将过滤后的消息转换为字典格式并追加
        for message in filtered_tool_call_messages:
            if isinstance(message, AssistantToolCallMessage):
                message_dict = format_assistant_tool_call_message(message)
            else:
                message_dict = format_message_for_llm(message)
            messages.append(message_dict)

        return messages

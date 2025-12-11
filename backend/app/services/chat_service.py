"""Chat service for RAG-based Q&A"""
import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Optional, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings
from app.models.chat import ChatMessageItemReq, ChatRequest, CollectedResponse
from app.models.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.utils.common import filter_dict
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.mcp.mcp_client import MCPClientManager
from app.services.prompt import get_default_system_prompt, get_prompt_for_title, get_prompt_with_mcp_servers, get_user_message_for_component_render
from pydantic import BaseModel


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.api_base,
        )
        self.mcp_manager = mcp_manager
        self.collected_content = ''  # 收集的完整响应内容
        self.collected_reasoning = ''  # 收集的推理内容
        self.collected_tool_call_messages: list[ToolCallMessage] = []  # 工具调用记录
        self.total_duration: Optional[float] = None  # 总耗时
        self.tool_calls_duration: Optional[float] = None  # 工具调用耗时
        self.reasoning_duration: Optional[float] = None  # 推理耗时
        self.content_duration: Optional[float] = None  # 内容生成耗时

    async def _stream_final_response(
        self,
        messages: list[dict],
        model: str,
    ) -> AsyncIterator[str]:
        """Stream final response"""
        start_time = get_current_time()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        logger.info("Using LLM model", model=model)
        start_reasoning = False
        start_content = False
        async for chunk in response:
            # For streaming responses, use delta instead of message
            delta = getattr(chunk.choices[0], 'delta', None)
            if delta and getattr(delta, 'reasoning_content', None):
                status = 'start' if not start_reasoning else 'continue'
                start_reasoning = True
                yield self.format_sse_message('reasoning', {
                    'status': status,
                    'content': delta.reasoning_content,
                })
            elif delta and getattr(delta, 'content', None):
                if start_reasoning:
                    start_reasoning = False
                    self.reasoning_duration = get_time_duration(start_time)
                    yield self.format_sse_message('reasoning', {
                        'status': 'done',
                        'duration': self.reasoning_duration,
                    })
                    start_time = get_current_time()

                status = 'start' if not start_content else 'continue'
                start_content = True
                yield self.format_sse_message('content', {
                    'status': status,
                    'content': delta.content,
                })

        if start_content:
            self.content_duration = get_time_duration(start_time)
            yield self.format_sse_message('content', {
                'status': 'done',
                'content': '',
                'duration': self.content_duration,
            })

    async def _call_llm_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
    ) -> AsyncGenerator[ToolCallMessage, ToolCallMessage]:
        """Call LLM with MCP tools and handle tool calls, streaming results

        Yields:
            tuple[str, list]: First element is SSE message (or None), second is accumulated messages
        Returns:
            list[AssistantMessage]: Final tool call messages
        """
        max_total_iterations = 10  # Prevent infinite loops
        max_iterations_by_tool = 5
        iterations_by_tool = {
            tool['function']['name']: max_iterations_by_tool for tool in tools}
        for iteration in range(max_total_iterations):
            logger.info("Tool call iteration started", iteration=iteration +
                        1, max_iterations=max_total_iterations)

            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages + self.collected_tool_call_messages,
                tools=tools if tools else None,
                stream=False,
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
            self.collected_tool_call_messages.append(assistant_message)
            yield assistant_message
            tool_count = len(
                assistant_message.tool_calls) if assistant_message.tool_calls else 0
            logger.info(
                "Tool calls required",
                tool_count=tool_count,
                iteration=iteration + 1,
            )
            # 只在 debug 模式下记录详细消息内容
            logger.debug(
                "Assistant message details",
                assistant_message=assistant_message.model_dump(
                    exclude_none=True),
            )

            # Execute tool calls and stream results
            for tool_call in assistant_message.tool_calls:
                tool_name = cast(str, tool_call.function.name)
                start_time = get_current_time()

                # Check if tool has reached max iterations BEFORE calling
                if iterations_by_tool[tool_name] <= 0:
                    logger.info(
                        "Tool max iterations reached, skipping",
                        tool_name=tool_name,
                        iteration=iteration + 1,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                        "content": f'Tool {tool_name} has hit max iterations, skipping'
                    })
                    self.collected_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message
                    continue

                # Decrement AFTER checking
                iterations_by_tool[tool_name] -= 1
                try:
                    # Call the tool via MCP manager
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)
                    logger.info(
                        "Calling MCP tool",
                        tool_name=tool_name,
                        iteration=iteration + 1,
                    )
                    logger.debug(
                        "MCP tool arguments",
                        tool_name=tool_name,
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

                    logger.info(
                        "MCP tool result received",
                        tool_name=tool_name,
                        result_length=len(content) if content else 0,
                    )
                    logger.debug(
                        "MCP tool result preview",
                        tool_name=tool_name,
                        result_preview=content[:200] + '...' +
                        content[-200:] if len(content) > 400 else content,
                    )

                    # Add tool result to messages
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": False,
                        "content": content,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    self.collected_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message

                except Exception as e:
                    logger.error(
                        "Failed to call tool",
                        error=e,
                        tool_name=tool_name,
                        iteration=iteration + 1,
                    )
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": str(e),
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    self.collected_tool_call_messages.append(
                        tool_call_result_message)
                    yield tool_call_result_message

        # If we hit max iterations, return error message
        logger.info(
            "Max iterations reached",
            max_iterations=max_total_iterations,
        )
        yield None
        return

    def format_sse_message(self, msg_type: str, data=None) -> str:
        """Format SSE (Server-Sent Events) message"""
        if data is None:
            return f"data: {json.dumps({'type': msg_type, 'data': {}}, ensure_ascii=False)}\n\n"

        # 如果 data 是 BaseModel
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="json", exclude_none=True)
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
            final_model = settings.llm.think_model if think_mode else settings.llm.model

            # Get MCP tools for LLM
            server_names = None if mcp_auto_mode else filter_dict(
                source_config.model_dump(), [True])
            tools = await self.mcp_manager.get_tools_for_llm(server_names, client_ip)
            if tools:
                # Call LLM with tools and stream results
                system_prompt, tool_call_user_message = get_prompt_with_mcp_servers(
                    user_message, mcp_auto_mode, server_names, client_ip)
                new_messages = self._compose_messages_without_tool_calls(
                    system_prompt, history,  tool_call_user_message)

                # Stream tool calls and collect messages
                start_time = get_current_time()
                async for message in self._call_llm_with_tools(
                    new_messages, final_model, tools
                ):
                    # Update accumulated messages
                    if message:
                        yield self.format_sse_message('tool_call', message.model_dump(exclude_none=True))

                if self.collected_tool_call_messages:
                    self.tool_calls_duration = get_time_duration(start_time)
                    yield self.format_sse_message('tool_call', {
                        'status': 'done',
                        'duration': self.tool_calls_duration,
                    })

            system_prompt = get_default_system_prompt(include_date=False)
            tool_call_user_message = get_user_message_for_component_render(
                user_message, self.collected_tool_call_messages)
            # 将工具调用历史拼接到用户消息中
            new_messages = self._compose_messages_with_tool_calls(
                system_prompt, history, self.collected_tool_call_messages, tool_call_user_message)
            async for chunk in self._stream_final_response(new_messages, final_model):
                yield chunk
            return

        except Exception as e:
            logger.error("Failed to stream message", error=e)
            raise

    async def generate_title(self, user_message: str) -> str:
        """Generate title for the chat"""
        system_prompt, new_user_message = get_prompt_for_title(
            user_message, self.collected_content)
        messages = self._compose_messages_without_tool_calls(
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
                exclude_none=True) for tool_call in self.collected_tool_call_messages],
            tool_calls_duration=self.tool_calls_duration,
            reasoning_duration=self.reasoning_duration,
            content_duration=self.content_duration,
            total_duration=self.total_duration,
        )

    @staticmethod
    def _compose_messages_without_tool_calls(
        system_prompt: str,
        history: list[ChatMessageItemReq],
        user_message: str,
    ) -> list[dict]:
        """Build prompt for LLM without context"""
        messages = [
            {"role": "system", "content": system_prompt}]

        history = history or []
        messages.extend(history)

        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _compose_messages_with_tool_calls(
        system_prompt: Optional[str],
        history: list[ChatMessageItemReq],
        tool_call_messages: list[ToolCallMessage],
        user_message: str,
    ) -> list[dict]:
        """Build prompt for LLM with context"""
        if not tool_call_messages:
            return ChatService._compose_messages_without_tool_calls(system_prompt, history, user_message)

        return ChatService._compose_messages_without_tool_calls(system_prompt, history + tool_call_messages, user_message)

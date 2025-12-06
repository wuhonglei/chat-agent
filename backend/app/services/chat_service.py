"""Chat service for RAG-based Q&A"""
import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Optional, cast

from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings
from app.models.chat import ChatMessageItemReq, ChatRequest, CollectedResponse
from app.models.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.utils.common import filter_dict
from app.utils.time import get_current_time, get_time_duration
from app.mcp.mcp_client import MCPClientManager
from app.services.prompt import get_default_system_prompt, get_prompt_for_title, get_prompt_with_mcp_servers
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
        self.collected_tool_calls: list[ToolCallMessage] = []  # 工具调用记录
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
        logger.info(f'model is {model}')
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
            logger.info(f"{'='*60}")
            logger.info(f'第 {iteration + 1} 轮迭代')

            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages + self.collected_tool_calls,
                tools=tools if tools else None,
                stream=False,
            )
            openai_message: ChatCompletionMessage = response.choices[0].message

            if not openai_message.tool_calls:
                logger.info(
                    "No tool calls, returning tool_call_messages. Assistant response: " + (openai_message.content if openai_message.content else 'empty'))
                yield None
                return

            # Handle tool calls
            assistant_message = AssistantToolCallMessage(**{
                'role': 'assistant',
                'content': openai_message.content,
                'tool_calls': openai_message.tool_calls,
                'reasoning_content': hasattr(openai_message, 'reasoning_content') and openai_message.reasoning_content or None,
            })
            self.collected_tool_calls.append(assistant_message)
            yield assistant_message
            logger.info(f'需要调用 {len(assistant_message.tool_calls)} 个工具:')
            logger.info(
                f'assistant_message is {assistant_message.model_dump(exclude_none=True)}')

            # Execute tool calls and stream results
            for tool_call in assistant_message.tool_calls:
                tool_name = cast(str, tool_call.function.name)
                start_time = get_current_time()

                # Check if tool has reached max iterations BEFORE calling
                if iterations_by_tool[tool_name] <= 0:
                    logger.info(
                        f"Tool {tool_name} has hit max iterations, skipping")
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                        "content": f'Tool {tool_name} has hit max iterations, skipping'
                    })
                    self.collected_tool_calls.append(tool_call_result_message)
                    yield tool_call_result_message
                    continue

                # Decrement AFTER checking
                iterations_by_tool[tool_name] -= 1
                try:
                    # Call the tool via MCP manager
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)
                    logger.info(
                        f"Calling MCP tool: {tool_name} with args: {arguments}")
                    result = await self.mcp_manager.call_tool(tool_name, arguments)
                    content = self.mcp_manager.format_mcp_result(result)
                    logger.info(
                        f"MCP tool result: {content[:200] + '...' + content[-200:] if len(content) > 200 else content}")

                    # Add tool result to messages
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": False,
                        "content": content,
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    self.collected_tool_calls.append(tool_call_result_message)
                    yield tool_call_result_message

                except Exception as e:
                    logger.error(f"Failed to call tool {tool_name}: {e}")
                    tool_call_result_message = ToolCallResultMessage(**{
                        "role": "tool",
                        "is_error": True,
                        "content": str(e),
                        "tool_call_id": tool_call.id,
                        "duration": get_time_duration(start_time),
                    })
                    self.collected_tool_calls.append(tool_call_result_message)
                    yield tool_call_result_message

        # If we hit max iterations, return error message
        logger.info('we have hit max iterations, returning tool_call_messages')
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
                new_user_message, system_prompt = get_prompt_with_mcp_servers(
                    user_message, mcp_auto_mode, server_names, client_ip)
                new_messages = self._compose_messages_without_tool_calls(
                    system_prompt, history,  new_user_message)

                # Stream tool calls and collect messages
                start_time = get_current_time()
                async for message in self._call_llm_with_tools(
                    new_messages, final_model, tools
                ):
                    # Update accumulated messages
                    if message:
                        yield self.format_sse_message('tool_call', message.model_dump(exclude_none=True))

                if self.collected_tool_calls:
                    self.tool_calls_duration = get_time_duration(start_time)
                    yield self.format_sse_message('tool_call', {
                        'status': 'done',
                        'duration': self.tool_calls_duration,
                    })

            system_prompt = get_default_system_prompt(include_date=False)
            # 将工具调用历史拼接到用户消息中
            new_messages = self._compose_messages_with_tool_calls(
                system_prompt, history, user_message, self.collected_tool_calls)
            async for chunk in self._stream_final_response(new_messages, final_model):
                yield chunk
            return

        except Exception as e:
            logger.error(f"Failed to stream message: {e}")
            raise

    async def generate_title(self, user_message: str) -> str:
        """Generate title for the chat"""
        new_user_message, system_prompt = get_prompt_for_title(
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
                exclude_none=True) for tool_call in self.collected_tool_calls],
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
        user_message: str,
        tool_call_messages: list[ToolCallMessage],
    ) -> list[dict]:
        """Build prompt for LLM with context"""
        if not tool_call_messages:
            return ChatService._compose_messages_without_tool_calls(system_prompt, history, user_message)

        return ChatService._compose_messages_without_tool_calls(system_prompt, history + tool_call_messages, user_message)

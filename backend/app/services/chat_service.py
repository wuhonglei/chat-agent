"""Chat service for RAG-based Q&A"""

import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings
from app.models.chat import ChatMessage, ChatRequest
from app.models.llm import AssistantMessage, ToolCallResultMessage
from app.utils.common import filter_dict
from app.mcp.mcp_client import MCPClientManager
from app.services.prompt import get_default_system_prompt, get_prompt_with_mcp_servers, get_prompt_with_tool_history


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.mcp_manager = mcp_manager

    async def _stream_final_response(
        self,
        messages: list[dict],
        model: str,
    ) -> AsyncIterator[str]:
        """Stream final response"""
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
                yield self._format_sse_message('reasoning', {
                    'status': status,
                    'content': delta.reasoning_content,
                })
            elif delta and getattr(delta, 'content', None):
                if start_reasoning:
                    start_reasoning = False
                    yield self._format_sse_message('reasoning', {
                        'status': 'done',
                    })

                status = 'start' if not start_content else 'continue'
                start_content = True
                yield self._format_sse_message('content', {
                    'status': status,
                    'content': delta.content,
                })

        if start_content:
            yield self._format_sse_message('content', {
                'status': 'done',
                'content': '',
            })

    async def _call_llm_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
    ) -> AsyncGenerator[tuple[str, list[AssistantMessage]], list[AssistantMessage]]:
        """Call LLM with MCP tools and handle tool calls, streaming results

        Yields:
            tuple[str, list]: First element is SSE message (or None), second is accumulated messages
        Returns:
            list[AssistantMessage]: Final tool call messages
        """
        max_iterations = 5  # Prevent infinite loops
        tool_call_messages: list[AssistantMessage] = []
        for iteration in range(max_iterations):
            logger.info(f'{'='*60}')
            logger.info(f'第 {iteration + 1} 轮迭代')

            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages + tool_call_messages,
                tools=tools if tools else None,
                stream=False,
            )
            assistant_message: AssistantMessage = response.choices[0].message

            # If no tool calls, yield and return the response
            if not assistant_message.tool_calls:
                logger.info(
                    "No tool calls, returning tool_call_messages. Assistant response: " + (assistant_message.content if assistant_message.content else 'empty'))
                yield self._format_sse_message('tool_call', {
                    'role': 'assistant',
                    'status': 'done',
                    'content': assistant_message.content or ''
                }), tool_call_messages
                return

            if not tool_call_messages:
                yield self._format_sse_message('tool_call', {
                    'role': 'assistant',
                    'status': 'start',
                }), tool_call_messages

            # Handle tool calls
            tool_call_messages.append(assistant_message)

            logger.info(f'需要调用 {len(assistant_message.tool_calls)} 个工具:')
            logger.info(
                f'assistant_message is {assistant_message.model_dump(exclude_none=True)}')

            # Execute tool calls and stream results
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    # Stream tool call start
                    yield self._format_sse_message(
                        'tool_call', {
                            'role': 'assistant',
                            'status': 'continue',
                            'content': assistant_message.content or '',
                            "tool_call_id": tool_call.id,
                            'tool_call': tool_call.model_dump(exclude_none=True)
                        }), tool_call_messages

                    # Call the tool via MCP manager
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)
                    logger.info(
                        f"Calling MCP tool: {tool_name} with args: {arguments}")
                    result = await self.mcp_manager.call_tool(tool_name, arguments)
                    content = self.mcp_manager.format_mcp_result(result)
                    logger.info(
                        f"MCP tool result: {content[:200] + '...' + content[-200:] if len(content) > 200 else content}")

                    # Stream tool call result
                    # 优先使用结构化内容，否则使用格式化的字符串内容
                    result_content = getattr(
                        result, 'structured_content') or content
                    yield self._format_sse_message(
                        'tool_call', {
                            'role': 'tool',
                            'status': 'continue',
                            'content': result_content,
                            "tool_call_id": tool_call.id,
                        }), tool_call_messages

                    # Add tool result to messages
                    tool_call_messages.append(ToolCallResultMessage(**{
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "is_error": False,
                        "content": content
                    }))

                except Exception as e:
                    logger.error(f"Failed to call tool {tool_name}: {e}")
                    error_msg = f"Error calling tool: {str(e)}"

                    # Stream error
                    yield self._format_sse_message(
                        'tool_call', {
                            'role': 'tool',
                            'status': 'error',
                            'content': error_msg,
                            "tool_call_id": tool_call.id,
                        }), tool_call_messages

                    tool_call_messages.append(ToolCallResultMessage(**{
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "is_error": True,
                        "content": error_msg
                    }))

        # If we hit max iterations, return error message
        logger.info('we have hit max iterations, returning tool_call_messages')
        yield self._format_sse_message('tool_call', {
            'role': 'assistant',
            'status': 'done',
            'content': 'we have hit max iterations, returning tool_call_messages'
        }), tool_call_messages
        return

    @staticmethod
    def _format_sse_message(msg_type: str, data=None) -> str:
        """Format SSE (Server-Sent Events) message"""
        if data is None:
            return f"data: {json.dumps({'type': msg_type, 'data': {}}, ensure_ascii=False)}\n\n"
        return f"data: {json.dumps({'type': msg_type, 'data': data}, ensure_ascii=False)}\n\n"

    async def stream_message(
        self,
        session_id: str,
        chat_request: ChatRequest
    ) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        try:
            # Choose between retrieval and MCP tool calling
            mcp_auto_mode = chat_request.mcp_auto_mode
            source_config = chat_request.source_config
            think_mode = chat_request.think_mode
            history = chat_request.history
            user_message = chat_request.message
            final_model = settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL

            # Get MCP tools for LLM
            server_names = None if mcp_auto_mode else filter_dict(
                source_config.model_dump(), [True])
            tools = await self.mcp_manager.get_tools_for_llm(server_names)
            tool_call_messages = []
            if tools:
                # Call LLM with tools and stream results
                new_user_message, system_prompt = get_prompt_with_mcp_servers(
                    user_message, mcp_auto_mode, server_names)
                new_messages = self._compose_messages_without_tool_calls(
                    system_prompt, history,  new_user_message)

                # Stream tool calls and collect messages
                async for sse_msg, accumulated_messages in self._call_llm_with_tools(
                    new_messages, settings.LLM_MODEL, tools
                ):
                    # Stream SSE messages
                    if sse_msg:
                        yield sse_msg
                    # Update accumulated messages
                    tool_call_messages = accumulated_messages

            system_prompt = get_default_system_prompt(include_date=False)
            # 将工具调用历史拼接到用户消息中
            new_messages = self._compose_messages_with_tool_calls(
                system_prompt, history, user_message, tool_call_messages)
            async for chunk in self._stream_final_response(new_messages, final_model):
                yield chunk
            return

        except Exception as e:
            logger.error(f"Failed to stream message: {e}")
            yield self._format_sse_message('error', str(e))

    @staticmethod
    def _compose_messages_without_tool_calls(
        system_prompt: str,
        history: list[ChatMessage],
        user_message: str,
    ) -> list[dict]:
        """Build prompt for LLM without context"""
        messages = [
            {"role": "system", "content": system_prompt}]

        history = history or []
        for msg in history[-5:]:  # Keep last 5 messages for context
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _compose_messages_with_tool_calls(
        system_prompt: Optional[str],
        history: list[ChatMessage],
        user_message: str,
        tool_call_messages: list[AssistantMessage],
    ) -> list[dict]:
        """Build prompt for LLM with context"""
        if not tool_call_messages:
            return ChatService._compose_messages_without_tool_calls(system_prompt, history, user_message)

        # 使用工具历史格式化用户消息
        formatted_user_message = get_prompt_with_tool_history(
            user_message, tool_call_messages)

        return ChatService._compose_messages_without_tool_calls(system_prompt, history, formatted_user_message)

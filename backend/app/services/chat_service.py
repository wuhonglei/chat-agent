"""Chat service for RAG-based Q&A"""

import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings
from app.models.chat import ChatMessage, ChatRequest
from app.utils.common import filter_dict
from app.mcp.mcp_client import MCPClientManager
from app.services.prompt import default_system_prompt, get_system_prompt_with_mcp_servers


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
        async for chunk in response:
            # For streaming responses, use delta instead of message
            delta = getattr(chunk.choices[0], 'delta', None)
            if delta and getattr(delta, 'reasoning_content', None):
                yield self._format_sse_message('reasoning', delta.reasoning_content)
            elif delta and getattr(delta, 'content', None):
                yield self._format_sse_message('content', delta.content)

        yield self._format_sse_message('done')

    async def _call_llm_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
    ) -> list[dict]:
        """Call LLM with MCP tools and handle tool calls (non-streaming)"""
        max_iterations = 5  # Prevent infinite loops
        tool_call_messages: list[dict] = []
        for iteration in range(max_iterations):
            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages + tool_call_messages,
                tools=tools if tools else None,
                stream=False,
            )
            assistant_message: ChatCompletionMessage = response.choices[0].message

            # If no tool calls, return the response
            if not assistant_message.tool_calls:
                logger.info("No tool calls, returning tool_call_messages")
                logger.info("final answer is: " + assistant_message.content)
                return tool_call_messages

            # Handle tool calls
            tool_call_messages.append(
                assistant_message.model_dump(exclude_none=True))

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)

                    # Call the tool via MCP manager
                    logger.info(
                        f"Calling MCP tool: {tool_name} with args: {arguments}")
                    result = await self.mcp_manager.call_tool(tool_name, arguments)

                    # Add tool result to messages
                    tool_call_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self.mcp_manager.format_mcp_result(result)
                    })

                except Exception as e:
                    logger.error(f"Failed to call tool {tool_name}: {e}")
                    tool_call_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error calling tool: {str(e)}"
                    })

        # If we hit max iterations, return error message
        return tool_call_messages

    @staticmethod
    def _format_sse_message(msg_type: str, data=None) -> str:
        """Format SSE (Server-Sent Events) message"""
        if data is None:
            return f"data: {json.dumps({'type': msg_type})}\n\n"
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
            if tools:
                # Call LLM with tools (non-streaming)
                system_prompt = get_system_prompt_with_mcp_servers(
                    mcp_auto_mode, server_names)
                new_messages = self._compose_messages(
                    user_message, history, None, system_prompt)
                tool_call_messages = await self._call_llm_with_tools(new_messages, settings.LLM_MODEL, tools)
            else:
                tool_call_messages = []

            new_messages = self._compose_messages(
                user_message, history, tool_call_messages, default_system_prompt)
            async for chunk in self._stream_final_response(new_messages, final_model):
                yield chunk
            return

        except Exception as e:
            logger.error(f"Failed to stream message: {e}")
            yield self._format_sse_message('error', str(e))

    def _compose_messages(
        self,
        user_message: str,
        history: list[ChatMessage] = None,
        tool_call_messages: list[dict] = None,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """Build prompt for LLM without context"""
        messages = [
            {"role": "system", "content": system_prompt or default_system_prompt}]

        history = history or []
        for msg in history[-5:]:  # Keep last 5 messages for context
            messages.append({"role": msg.role, "content": msg.content})

        messages = messages + (tool_call_messages or [])
        messages.append({"role": "user", "content": user_message})
        return messages

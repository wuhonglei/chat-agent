"""Base Agent class for all agents"""

from collections.abc import AsyncGenerator
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.protocols import format_tool_result_message, format_tool_use_message
from app.schemas.chat import (
    ChatMessage,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.services.base_service.llm_service import LLMService
from app.utils.common import normalize_to_dict
from app.utils.message import format_chat_message_for_llm
from app.utils.model import format_sse_message


class BaseAgent(LLMService):
    """Agent基类，定义所有agent的通用接口和共享功能；继承 LLMService 获得 LLM 调用能力"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig):
        """初始化agent，接收思考模式和LLM配置

        Args:
            think_mode: 是否使用思考模式
            llm_config: LLM配置，用于初始化客户端和模型配置
        """
        super().__init__(llm_config=llm_config, think_mode=think_mode)

    async def stream_execute(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """流式执行agent的核心逻辑，子类必须实现

        Yields:
            str: SSE格式的消息
        """
        raise NotImplementedError("This agent does not support non-streaming execution")

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """非流式执行agent的核心逻辑，子类可选实现

        默认实现抛出 NotImplementedError，子类如果需要非流式执行可以重写此方法
        """
        raise NotImplementedError("This agent does not support non-streaming execution")

    @staticmethod
    def format_sse_message(msg_type: str, data: Any = None) -> str:
        return format_sse_message(msg_type, data)

    def _compose_history_messages(
        self,
        history_messages: list[ChatMessage],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for msg in history_messages or []:
            messages.extend(self._format_history_message_for_llm(msg))
        return messages

    def _format_history_message_for_llm(
        self, message: ChatMessage
    ) -> list[dict[str, Any]]:
        if message.role != "assistant":
            return [format_chat_message_for_llm(message, clear_reasoning_content=True)]

        blocks = message.content_blocks or []
        if not any(
            isinstance(block, (ToolUseBlock, ToolResultBlock)) for block in blocks
        ):
            return [format_chat_message_for_llm(message, clear_reasoning_content=True)]

        formatted: list[dict[str, Any]] = []
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        idx = 0

        def flush_plain_assistant() -> None:
            content = "".join(text_parts)
            if not content and not reasoning_parts:
                return
            formatted.append({"role": "assistant", "content": content})
            text_parts.clear()
            reasoning_parts.clear()

        while idx < len(blocks):
            block = blocks[idx]
            if isinstance(block, ThinkingBlock):
                reasoning_parts.append(block.text)
                idx += 1
                continue
            if not isinstance(block, (ToolUseBlock, ToolResultBlock)):
                text = getattr(block, "text", None)
                if text:
                    text_parts.append(text)
                idx += 1
                continue

            if isinstance(block, ToolUseBlock):
                tool_calls: list[ChatCompletionMessageFunctionToolCall] = []
                # 将连续的 tool-use block 合并为一条 assistant 工具调用消息。
                while idx < len(blocks):
                    tool_use_block = blocks[idx]
                    if not isinstance(tool_use_block, ToolUseBlock):
                        break
                    if tool_use_block.tool_call_id:
                        arguments_text = tool_use_block.arguments_text or "{}"
                        try:
                            tool_call = (
                                ChatCompletionMessageFunctionToolCall.model_validate(
                                    {
                                        "id": tool_use_block.tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_use_block.name or "",
                                            "arguments": arguments_text,
                                        },
                                    }
                                )
                            )
                        except Exception:
                            tool_call = (
                                ChatCompletionMessageFunctionToolCall.model_validate(
                                    {
                                        "id": tool_use_block.tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_use_block.name or "",
                                            "arguments": "{}",
                                        },
                                    }
                                )
                            )
                        tool_calls.append(tool_call)
                    idx += 1

                assistant_tool_message = ToolUseMessage(
                    role="assistant",
                    content="".join(text_parts),
                    reasoning_content="".join(reasoning_parts) or None,
                    tool_calls=tool_calls or None,
                )
                formatted.append(
                    format_tool_use_message(
                        assistant_tool_message,
                        clear_reasoning_content=True,
                    )
                )
                text_parts.clear()
                reasoning_parts.clear()
                continue

            flush_plain_assistant()
            # 先消费连续的 tool-result block，再回到混合 block 的解析流程。
            while idx < len(blocks):
                tool_result_block = blocks[idx]
                if not isinstance(tool_result_block, ToolResultBlock):
                    break
                formatted.append(
                    format_tool_result_message(
                        ToolResultMessage(
                            role="tool",
                            tool_call_id=tool_result_block.tool_call_id,
                            is_error=tool_result_block.is_error,
                            content=tool_result_block.content,
                            summary=None,
                        )
                    )
                )
                idx += 1

        flush_plain_assistant()
        return formatted

    def _compose_messages(
        self,
        system_prompt: str,
        history_messages: list[ChatMessage],
        user_message: str,
        tool_call_messages: list[ToolMessage] | None = None,
    ) -> list[dict[str, Any]]:
        """Build prompt for LLM

        Args:
            system_prompt: System prompt message
            history_messages: Conversation history messages
            user_message: Current user message
            tool_call_messages: Optional tool call messages (assistant tool calls and tool results)

        Returns:
            Message list with correct order: system_prompt -> history -> user_message -> tool_call_messages
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.extend(self._compose_history_messages(history_messages))

        messages.append({"role": "user", "content": user_message})

        # 如果有 tool_call_messages，过滤后转换为字典格式并追加
        if not tool_call_messages:
            return messages

        for message in tool_call_messages:
            message_dict = normalize_to_dict(message)
            messages.append(message_dict)

        return messages

"""Base Agent class for all agents"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from app.schemas.chat import ChatMessageItem
from app.schemas.config import LLMConfig
from app.schemas.content import ContentPart
from app.schemas.llm import ToolMessage
from app.schemas.token_stats import BaseTokenStats, TokenUsage
from app.services.base_service.llm_service import LLMService
from app.utils.common import normalize_to_dict
from app.utils.content import content_parts_to_openai_content
from app.utils.message import format_chat_message_for_llm
from app.utils.model import format_sse_message


class BaseAgent(ABC, LLMService):
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

    def _create_token_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> TokenUsage:
        """
        创建 TokenUsage 对象（辅助方法）

        Args:
            prompt_tokens: 输入 token 数量
            completion_tokens: 输出 token 数量

        Returns:
            TokenUsage 对象
        """
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    @abstractmethod
    def create_token_stats(
        self, *args: Any, **kwargs: dict[str, Any]
    ) -> BaseTokenStats:
        """
        创建 token 统计对象（抽象方法，子类必须实现）

        Args:
            kwargs: 子类特定的额外参数

        Returns:
            BaseTokenStats 对象
        """
        pass

    def _compose_messages(
        self,
        system_prompt: str,
        history_messages: list[ChatMessageItem],
        user_message: str | list[ContentPart],
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
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        history = history_messages or []
        for msg in history:
            msg_dict = format_chat_message_for_llm(msg, clear_reasoning_content=True)
            messages.append(msg_dict)

        messages.append(
            {"role": "user", "content": content_parts_to_openai_content(user_message)}
        )

        # 如果有 tool_call_messages，过滤后转换为字典格式并追加
        if not tool_call_messages:
            return messages

        for message in tool_call_messages:
            message_dict = normalize_to_dict(message)
            messages.append(message_dict)

        return messages

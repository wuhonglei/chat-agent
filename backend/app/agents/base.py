"""Base Agent class for all agents"""
from collections.abc import AsyncGenerator
from typing import Optional
from abc import ABC

from openai import AsyncOpenAI

from app.schemas.chat import ChatMessageItemReq
from app.schemas.config import LLMConfig
from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
from app.utils.message import clear_reasoning_content, format_message_for_llm, format_assistant_tool_call_message
from app.utils.model import format_sse_message


class BaseAgent(ABC):
    """Agent基类，定义所有agent的通用接口和共享功能"""

    def __init__(self, llm_config: LLMConfig):
        """初始化agent，接收依赖项以访问所需资源

        Args:
            llm_config: LLM配置，用于初始化客户端和模型配置
        """
        # 根据传入的llm_config初始化OpenAI客户端
        self.client = AsyncOpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
        )
        # 模型配置（从传入的llm_config获取）
        self.model_config = llm_config

    async def stream_execute(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        """流式执行agent的核心逻辑，子类必须实现

        Yields:
            str: SSE格式的消息
        """
        pass

    async def execute(self, *args, **kwargs):
        """非流式执行agent的核心逻辑，子类可选实现

        默认实现抛出 NotImplementedError，子类如果需要非流式执行可以重写此方法
        """
        raise NotImplementedError(
            "This agent does not support non-streaming execution")

    @staticmethod
    def format_sse_message(msg_type: str, data=None) -> str:
        return format_sse_message(msg_type, data)

    def _compose_messages(
        self,
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

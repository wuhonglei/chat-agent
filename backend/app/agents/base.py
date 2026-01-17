"""Base Agent class for all agents"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, Literal, overload

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AsyncOpenAI,
    RateLimitError,
)
from openai._streaming import AsyncStream
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from app.schemas.chat import ChatMessageItem
from app.schemas.config import LLMConfig
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.schemas.token_stats import BaseTokenStats, TokenUsage
from app.utils.common import normalize_to_dict
from app.utils.logger import logger
from app.utils.message import format_chat_message_for_llm
from app.utils.model import format_sse_message, get_model_extra_body
from app.utils.token import TokenCalculator


class BaseAgent(ABC):
    """Agent基类，定义所有agent的通用接口和共享功能"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig):
        """初始化agent，接收思考模式和LLM配置

        Args:
            think_mode: 是否使用思考模式
            llm_config: LLM配置，用于初始化客户端和模型配置
        """
        # 根据传入的llm_config初始化OpenAI客户端
        self.client = AsyncOpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
        )
        # 模型配置（从传入的llm_config获取）
        self.model_config = llm_config
        self.think_mode = think_mode
        self.token_calculator = TokenCalculator(llm_config.model_name)
        self.model_limit = self.token_calculator.get_max_context_tokens()

    async def stream_execute(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        """流式执行agent的核心逻辑，子类必须实现

        Yields:
            str: SSE格式的消息
        """
        raise NotImplementedError("This agent does not support non-streaming execution")

    async def execute(self, *args, **kwargs):
        """非流式执行agent的核心逻辑，子类可选实现

        默认实现抛出 NotImplementedError，子类如果需要非流式执行可以重写此方法
        """
        raise NotImplementedError("This agent does not support non-streaming execution")

    @staticmethod
    def format_sse_message(msg_type: str, data=None) -> str:
        return format_sse_message(msg_type, data)

    @property
    def model_name(self) -> str:
        """
        根据 think_mode 获取对应的模型名称

        Returns:
            str: 模型名称
        """
        return (
            self.model_config.think_model_name
            if self.think_mode
            else self.model_config.model_name
        )

    @property
    def extra_body(self) -> dict[str, Any]:
        """
        根据 think_mode 获取模型额外参数

        Returns:
            dict[str, Any]: 模型额外参数
        """
        return get_model_extra_body(self.think_mode)

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

    @overload
    async def _call_llm_api(
        self,
        model: str,
        messages: list[dict],
        stream: Literal[False],
        *,
        tools: list[dict] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatCompletion: ...

    @overload
    async def _call_llm_api(
        self,
        model: str,
        messages: list[dict],
        stream: Literal[True],
        *,
        tools: list[dict] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncStream[ChatCompletionChunk]: ...

    async def _call_llm_api(
        self,
        model: str,
        messages: list[dict],
        stream: bool,
        *,
        tools: list[dict] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """
        调用 LLM API 的统一方法，包含错误处理

        Args:
            model: 模型名称
            messages: 消息列表
            stream: 是否使用流式响应
                - False: 返回 ChatCompletion 对象
                - True: 返回 AsyncStream[ChatCompletionChunk] 异步迭代器
            tools: 工具列表（可选）
            parallel_tool_calls: 是否启用并行工具调用（可选）
            extra_body: 额外参数（可选）

        Returns:
            - 当 stream=False 时，返回 ChatCompletion 对象
            - 当 stream=True 时，返回 AsyncStream[ChatCompletionChunk] 异步迭代器

        Raises:
            APIError: 各种 API 相关错误
            Exception: 其他未预期的错误
        """
        # 构建 API 调用参数
        api_params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if parallel_tool_calls is not None:
            api_params["parallel_tool_calls"] = parallel_tool_calls

        if tools is not None:
            api_params["tools"] = tools
        else:
            api_params["tool_choice"] = "none"

        if extra_body is not None:
            api_params["extra_body"] = extra_body

        # 准备日志上下文
        log_context = {
            "model": model,
            "stream": stream,
            "extra_body": extra_body,
            "messages_count": len(messages),
        }
        if tools is not None:
            log_context["tools_count"] = len(tools)

        try:
            logger.info("Calling LLM API", **log_context)
            response = await self.client.chat.completions.create(**api_params)
            return response
        except APIConnectionError as e:
            logger.error(
                "Failed to connect to LLM API",
                error=str(e),
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise  # 重新抛出异常，让上层处理
        except RateLimitError as e:
            logger.error(
                "LLM API rate limit exceeded",
                error=str(e),
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise  # 重新抛出异常，让上层处理
        except APIStatusError as e:
            logger.error(
                "LLM API returned an error status",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e, "status_code", None),
                **log_context,
                exc_info=True,
            )
            raise  # 重新抛出异常，让上层处理
        except APIError as e:
            logger.error(
                "LLM API error occurred",
                error=str(e),
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise  # 重新抛出异常，让上层处理
        except Exception as e:
            logger.error(
                "Unexpected error during LLM API call",
                error=str(e),
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise  # 重新抛出异常，让上层处理

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
        user_message: str,
        tool_call_messages: list[ToolCallMessage] | None = None,
    ) -> list[dict]:
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

        history = history_messages or []
        for msg in history:
            msg_dict = format_chat_message_for_llm(msg, keep_reasoning=False)
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
                for tool_call in message.tool_calls or []:
                    if tool_call.id in valid_tool_call_ids:
                        assistant_tool_call_ids.add(tool_call.id)

        # 第三步：只保留正确的工具调用（ToolCallResultMessage is_error=False 且有对应的 assistant 消息）
        filtered_tool_call_messages = []
        for message in tool_call_messages:
            if isinstance(message, AssistantToolCallMessage):
                # 保留 assistant 工具调用中有效的工具调用
                # 使用 model_copy() 创建副本，避免修改原始对象
                filtered_tool_calls = [
                    tool_call
                    for tool_call in (message.tool_calls or [])
                    if tool_call.id in assistant_tool_call_ids
                ]
                if filtered_tool_calls:
                    # 创建新对象副本，只更新 tool_calls 字段
                    filtered_message = message.model_copy(
                        update={"tool_calls": filtered_tool_calls}
                    )
                    filtered_tool_call_messages.append(filtered_message)
            elif isinstance(message, ToolCallResultMessage):
                # 只保留没有错误且有对应 assistant 消息的工具调用结果
                if (
                    not message.is_error
                    and message.tool_call_id in assistant_tool_call_ids
                ):
                    filtered_tool_call_messages.append(message)

        # 将过滤后的消息转换为字典格式并追加
        for message in filtered_tool_call_messages:
            message_dict = normalize_to_dict(message)
            messages.append(message_dict)

        return messages

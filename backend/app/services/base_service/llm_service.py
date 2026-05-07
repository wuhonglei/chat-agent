"""LLM 调用服务，封装模型 API 调用与相关配置"""

from __future__ import annotations

from typing import Any, Literal, cast, overload

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

from app.schemas.config import LLMConfig
from app.utils.logger import logger
from app.utils.model import get_model_extra_body
from app.utils.token import TokenCalculator


class LLMService:
    """LLM 调用服务

    封装 OpenAI 兼容 API 的客户端、模型配置、思考模式及统一调用方法，
    供 Agent 等调用方使用。
    """

    def __init__(self, llm_config: LLMConfig, think_mode: bool = False):
        """
        初始化 LLM 服务。

        Args:
            llm_config: LLM 配置（API 密钥、地址、模型名等）
            think_mode: 是否使用思考模式（影响 model_name 与 extra_body）
        """
        self._client = AsyncOpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
        )
        self._model_config = llm_config
        self._think_mode = think_mode
        self._token_calculator = TokenCalculator(llm_config.model_name)
        self._model_limit = self._token_calculator.get_max_context_tokens()

    @property
    def client(self) -> AsyncOpenAI:
        """OpenAI 兼容的异步客户端（只读）。"""
        return self._client

    @property
    def model_config(self) -> LLMConfig:
        """当前 LLM 配置（只读）。"""
        return self._model_config

    @property
    def think_mode(self) -> bool:
        """是否处于思考模式。"""
        return self._think_mode

    @think_mode.setter
    def think_mode(self, value: bool) -> None:
        """按请求设置思考模式（供 Agent 每请求覆盖）。"""
        object.__setattr__(self, "_think_mode", value)

    @property
    def token_calculator(self) -> TokenCalculator:
        """Token 计算器（只读）。"""
        return self._token_calculator

    @property
    def model_limit(self) -> int:
        """模型上下文 token 上限。"""
        return self._model_limit

    @property
    def model_name(self) -> str:
        """当前使用的模型名称。"""
        return self._model_config.model_name

    @property
    def extra_body(self) -> dict[str, Any]:
        """根据 think_mode 返回模型 extra_body 参数。"""
        return get_model_extra_body(self._think_mode)

    @overload
    async def call_llm_api(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[False],
        *,
        tools: list[dict[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion: ...

    @overload
    async def call_llm_api(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[True],
        *,
        tools: list[dict[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> AsyncStream[ChatCompletionChunk]: ...

    @overload
    async def call_llm_api(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        *,
        tools: list[dict[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]: ...

    async def call_llm_api(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        *,
        tools: list[dict[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        extra_body: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """
        调用 LLM API 的统一方法，包含错误处理。

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
        api_params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if parallel_tool_calls is not None:
            api_params["parallel_tool_calls"] = parallel_tool_calls

        if tools is not None:
            api_params["tools"] = tools

        if extra_body is not None:
            api_params["extra_body"] = extra_body

        if max_tokens is not None:
            api_params["max_tokens"] = max_tokens

        log_context: dict[str, Any] = {
            "model": model,
            "stream": stream,
            "extra_body": extra_body,
            "messages_count": len(messages),
        }
        if tools is not None:
            log_context["tools_count"] = len(tools)

        try:
            logger.info("Calling LLM API", **log_context)
            response = await self._client.chat.completions.create(**api_params)
            return cast(ChatCompletion | AsyncStream[ChatCompletionChunk], response)
        except APIConnectionError as e:
            logger.error(
                "Failed to connect to LLM API",
                error=e,
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise
        except RateLimitError as e:
            logger.error(
                "LLM API rate limit exceeded",
                error=e,
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise
        except APIStatusError as e:
            logger.error(
                "LLM API returned an error status",
                error=e,
                error_type=type(e).__name__,
                status_code=getattr(e, "status_code", None),
                **log_context,
                exc_info=True,
            )
            raise
        except APIError as e:
            logger.error(
                "LLM API error occurred",
                error=e,
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during LLM API call",
                error=e,
                error_type=type(e).__name__,
                **log_context,
                exc_info=True,
            )
            raise

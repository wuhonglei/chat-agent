"""LLM 调用服务，封装模型 API 调用与相关配置"""

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast, overload

from langfuse.openai import AsyncOpenAI  # type: ignore[attr-defined]
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    RateLimitError,
)
from openai._streaming import AsyncStream
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from app.core.config import settings
from app.core.observability import get_langfuse, is_enabled
from app.schemas.config import LLMConfig
from app.services.base_service.llm_error_handling import (
    LLMCallError,
    build_circuit_open_error,
    build_llm_call_error,
    build_retry_delay_ms,
    classify_error,
    counts_toward_circuit,
    get_circuit_breaker,
)
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
            max_retries=0,
        )
        self._model_config = llm_config
        self._think_mode = think_mode
        self._token_calculator = TokenCalculator(
            llm_config.model_name, llm_config.context_limit
        )
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
        stream_options: dict[str, Any] | None = None,
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
        stream_options: dict[str, Any] | None = None,
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
        stream_options: dict[str, Any] | None = None,
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
        stream_options: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """
        调用 LLM API 的统一方法，包含错误分类、重试与熔断。

        重试仅覆盖 ``chat.completions.create`` 建连阶段；拿到 stream 后
        的 chunk 消费失败不在此重试。

        Args:
            model: 模型名称
            messages: 消息列表
            stream: 是否使用流式响应
                - False: 返回 ChatCompletion 对象
                - True: 返回 AsyncStream[ChatCompletionChunk] 异步迭代器
            tools: 工具列表（可选）
            parallel_tool_calls: 是否启用并行工具调用（可选）
            extra_body: 额外参数（可选）
            stream_options: 流式参数（可选，仅 stream=True 时生效）

        Returns:
            - 当 stream=False 时，返回 ChatCompletion 对象
            - 当 stream=True 时，返回 AsyncStream[ChatCompletionChunk] 异步迭代器

        Raises:
            LLMCallError: 建连失败且不可重试/重试耗尽/熔断打开
            asyncio.CancelledError: 调用被取消
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

        if stream and stream_options is not None:
            api_params["stream_options"] = stream_options

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

        reliability = settings.llm_reliability
        breaker = get_circuit_breaker(self._model_config.api_base, reliability)

        if breaker.is_open():
            raise build_circuit_open_error()

        trace_enabled = is_enabled()
        langfuse_client = get_langfuse()

        def mark_observation_error(error_type: str) -> None:
            if not trace_enabled or langfuse_client is None:
                return
            try:
                langfuse_client.update_current_span(
                    level="ERROR",
                    status_message=error_type,
                )
            except Exception as update_exc:
                logger.warning(
                    "Failed to update LLM observation error status",
                    error=update_exc,
                    error_type=type(update_exc).__name__,
                    llm_error_type=error_type,
                )

        max_attempts = reliability.retry_max_attempts
        attempt = 1
        while True:
            try:
                logger.info(
                    "Calling LLM API",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    **log_context,
                )
                response = await self._client.chat.completions.create(**api_params)
                breaker.record_success()
                return cast(ChatCompletion | AsyncStream[ChatCompletionChunk], response)
            except asyncio.CancelledError:
                breaker.release_probe()
                raise
            except Exception as e:
                mark_observation_error(type(e).__name__)
                retriable, reason = classify_error(e)
                self._log_llm_exception(e, log_context)

                if retriable and attempt < max_attempts:
                    wait_ms = build_retry_delay_ms(
                        attempt,
                        e,
                        base_delay_ms=reliability.retry_base_delay_ms,
                        cap_delay_ms=reliability.retry_cap_delay_ms,
                    )
                    logger.warning(
                        "Transient LLM error; retrying",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        wait_ms=wait_ms,
                        reason=reason,
                        error=e,
                        error_type=type(e).__name__,
                        **log_context,
                    )
                    await asyncio.sleep(wait_ms / 1000)
                    attempt += 1
                    continue

                if counts_toward_circuit(reason):
                    breaker.record_failure()
                else:
                    breaker.release_probe()

                raise build_llm_call_error(e, reason) from e

    @staticmethod
    def _log_llm_exception(
        exc: Exception,
        log_context: dict[str, Any],
    ) -> None:
        if isinstance(exc, APIConnectionError):
            logger.error(
                "Failed to connect to LLM API",
                error=exc,
                error_type=type(exc).__name__,
                **log_context,
                exc_info=True,
            )
            return
        if isinstance(exc, RateLimitError):
            logger.error(
                "LLM API rate limit exceeded",
                error=exc,
                error_type=type(exc).__name__,
                **log_context,
                exc_info=True,
            )
            return
        if isinstance(exc, APIStatusError):
            logger.error(
                "LLM API returned an error status",
                error=exc,
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
                **log_context,
                exc_info=True,
            )
            return
        if isinstance(exc, APIError):
            logger.error(
                "LLM API error occurred",
                error=exc,
                error_type=type(exc).__name__,
                **log_context,
                exc_info=True,
            )
            return
        if isinstance(exc, LLMCallError):
            logger.error(
                "LLM call error",
                error=exc,
                error_type=type(exc).__name__,
                reason=exc.reason,
                detail=exc.detail,
                **log_context,
                exc_info=True,
            )
            return
        logger.error(
            "Unexpected error during LLM API call",
            error=exc,
            error_type=type(exc).__name__,
            **log_context,
            exc_info=True,
        )

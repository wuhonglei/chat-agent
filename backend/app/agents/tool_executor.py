"""Tool execution helpers for MCP-backed tool calls."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from toolz import get

from app.agents.tool_batch_planner import plan_tool_batch_segments
from app.agents.tool_call_guardrail import (
    GuardrailDecisionKind,
    ToolCallGuardrail,
)
from app.agents.utils import TavilyResultProcessor
from app.agents.utils.shell_result_processor import build_shell_display_items
from app.core.config import settings
from app.core.observability import (
    mark_observation_error,
    observation_span,
    score_observation,
)
from app.mcp.client import MCPClientManager
from app.mcp.constants import (
    CODE_SERVER,
    SHELL_SERVER,
    SKIP_TOOL_RESULT_COMPACTION_SERVERS,
    TAVILY_SERVER,
    WEB_PAGES_EXTRACT_BARE,
)
from app.mcp.errors import ToolArgumentValidationError
from app.mcp.tool_naming import is_llm_tool
from app.schemas.llm import ToolResultMessage
from app.utils.common import normalize_url
from app.utils.context import set_request_context
from app.utils.context_compactor import ContextCompactor
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator


class ToolExecutor:
    """Execute MCP tools and compact their results."""

    OVERALL_TIMEOUT_SECONDS = 90

    def __init__(
        self,
        mcp_manager: MCPClientManager,
        user_message: str,
        model_name: str,
        context_limit: int,
    ) -> None:
        self.mcp_manager = mcp_manager
        self.current_user_message = user_message
        self.current_user_id: str | None = None
        self.current_conversation_id: str | None = None
        self.tool_result_compression = settings.chat_context.tool_result_compression
        self.compactor = ContextCompactor(
            embedding_model=settings.embedding_model,
            tool_result_compression_config=self.tool_result_compression,
        )
        self.token_calculator = TokenCalculator(model_name, context_limit)
        self.token_threshold: int = self.token_calculator.get_compression_threshold(0.5)
        self.guardrail = ToolCallGuardrail()

    def reset_for_request(
        self,
        user_message: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        self.current_user_message = user_message
        self.current_user_id = user_id
        self.current_conversation_id = conversation_id
        self.guardrail.reset()

        # Set contextvars for tools to access
        set_request_context(user_id=user_id, conversation_id=conversation_id)

    async def execute_tool_calls_parallel(
        self,
        *,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        current_iteration: int,
        extracted_urls: set[str],
        on_arguments_recorded: Callable[[str, dict[str, Any], str], None],
        on_urls_extracted: Callable[[set[str]], None],
    ) -> list[ToolResultMessage]:
        active_calls = [tc for tc in tool_calls if tc is not None]
        segments = plan_tool_batch_segments(active_calls)
        results_by_id: dict[str, ToolResultMessage] = {}
        timeout_content = (
            f"⏱️ 工具调用整体超时（超过 {self.OVERALL_TIMEOUT_SECONDS} 秒）"
        )

        async def _run_all_segments() -> None:
            for segment in segments:
                if self.guardrail.halted:
                    for tool_call in segment:
                        results_by_id[tool_call.id] = ToolResultMessage(
                            role="tool",
                            is_error=True,
                            content=self.guardrail.synthetic_halt_message(
                                tool_call.function.name
                            ),
                            tool_call_id=tool_call.id,
                        )
                    continue

                tasks = [
                    asyncio.ensure_future(
                        self.execute_single_tool(
                            tool_call=tool_call,
                            current_iteration=current_iteration,
                            extracted_urls=extracted_urls,
                            on_arguments_recorded=on_arguments_recorded,
                            on_urls_extracted=on_urls_extracted,
                        )
                    )
                    for tool_call in segment
                ]
                segment_results = list(await asyncio.gather(*tasks))
                for tool_call, result in zip(segment, segment_results, strict=True):
                    results_by_id[tool_call.id] = result

        try:
            await asyncio.wait_for(
                _run_all_segments(),
                timeout=self.OVERALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Parallel tool execution overall timeout",
                timeout=self.OVERALL_TIMEOUT_SECONDS,
                total_calls=len(active_calls),
                iteration=current_iteration + 1,
            )
            for tool_call in active_calls:
                if tool_call.id not in results_by_id:
                    results_by_id[tool_call.id] = ToolResultMessage(
                        role="tool",
                        is_error=True,
                        content=timeout_content,
                        tool_call_id=tool_call.id,
                    )

        return [results_by_id[tc.id] for tc in active_calls]

    async def execute_single_tool(
        self,
        *,
        tool_call: ChatCompletionMessageFunctionToolCall,
        current_iteration: int,
        extracted_urls: set[str],
        on_arguments_recorded: Callable[[str, dict[str, Any], str], None],
        on_urls_extracted: Callable[[set[str]], None],
    ) -> ToolResultMessage:
        tool_name = tool_call.function.name
        start_time = get_current_time()
        with observation_span(
            tool_name,
            as_type="tool",
            input=tool_call.function.arguments,
        ) as tool_span:
            try:
                arguments = json.loads(tool_call.function.arguments)
                if is_llm_tool(tool_name, TAVILY_SERVER, WEB_PAGES_EXTRACT_BARE) and (
                    urls := get("urls", arguments)
                ):
                    normalized_urls = {normalize_url(url) for url in urls if url}
                    new_urls = normalized_urls - extracted_urls
                    if not new_urls:
                        logger.info(
                            "All URLs already extracted, skipping web_pages_extract",
                            urls=urls,
                            iteration=current_iteration + 1,
                        )
                        skip_message = ToolResultMessage(
                            role="tool",
                            is_error=False,
                            tool_call_id=tool_call.id,
                            content="⚠️ 提示：这些 URL 已经在之前的调用中提取过了。请检查历史工具调用结果，如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
                        )
                        self._score_tool_success(
                            tool_span,
                            success=True,
                            error_type=None,
                        )
                        return skip_message
                    on_urls_extracted(new_urls)
                    arguments["urls"] = new_urls
                    logger.info(
                        "Filtered URLs for web_pages_extract",
                        original_count=len(urls),
                        new_count=len(new_urls),
                        iteration=current_iteration + 1,
                    )

                decision = self.guardrail.before_call(tool_name, arguments)
                if decision.kind in (
                    GuardrailDecisionKind.BLOCK,
                    GuardrailDecisionKind.HALT,
                ):
                    blocked_message = ToolResultMessage(
                        role="tool",
                        is_error=True,
                        tool_call_id=tool_call.id,
                        content=decision.message,
                    )
                    logger.warning(
                        "Tool call blocked by guardrail",
                        tool_name=tool_name,
                        tool_call_id=tool_call.id,
                        decision=decision.kind.value,
                        iteration=current_iteration + 1,
                    )
                    self._score_tool_success(
                        tool_span,
                        success=False,
                        error_type=decision.kind.value,
                    )
                    return blocked_message

                on_arguments_recorded(tool_name, arguments, tool_call.id)
                logger.info(
                    "Calling MCP tool",
                    tool_name=tool_name,
                    tool_call_id=tool_call.id,
                    iteration=current_iteration + 1,
                    arguments=arguments,
                )
                result, call_warnings = await self.mcp_manager.call_tool(
                    tool_name, arguments
                )
                content = self.mcp_manager.format_mcp_result(result)
                tool_call_result_message = ToolResultMessage(
                    role="tool",
                    content=content,
                    is_error=len(content or "") == 0,
                    tool_call_id=tool_call.id,
                )
                server_name = self.mcp_manager.get_server_for_tool(tool_name)
                skip_compaction = server_name in SKIP_TOOL_RESULT_COMPACTION_SERVERS
                if skip_compaction:
                    logger.info(
                        "Skipping tool result compaction for agent skills workspace tool",
                        tool_name=tool_name,
                        tool_call_id=tool_call.id,
                    )
                elif (
                    server_name == TAVILY_SERVER
                    and result.structured_content is not None
                ):
                    tool_call_result_message = await self._apply_tavily_compaction(
                        tool_name=tool_name,
                        structured_content=result.structured_content,
                        tool_call_result_message=tool_call_result_message,
                    )
                else:
                    tool_call_result_message = (
                        await self._compact_tool_result_if_needed(
                            tool_call_result_message
                        )
                    )

                if (
                    server_name == SHELL_SERVER
                    and result.structured_content is not None
                ):
                    tool_call_result_message = tool_call_result_message.model_copy(
                        update={
                            "structured_content_for_display": build_shell_display_items(
                                result.structured_content
                            )
                        }
                    )

                content = tool_call_result_message.content or ""
                warning_msg = self._build_tool_warning_message(tool_name, call_warnings)
                if warning_msg:
                    content = warning_msg + content
                    tool_call_result_message.content = content
                    logger.info(
                        "Added tool warnings to tool result",
                        tool_name=tool_name,
                        warnings=call_warnings,
                    )
                success, error_type, outcome_meta = self._resolve_tool_outcome(
                    server_name=server_name,
                    content=content,
                    structured_content=result.structured_content
                    if isinstance(result.structured_content, dict)
                    else None,
                )
                tool_call_result_message = tool_call_result_message.model_copy(
                    update={"is_error": not success}
                )
                guardrail_suffix = self.guardrail.record_outcome(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=success,
                    content=content,
                )
                if guardrail_suffix:
                    content = content + guardrail_suffix
                    tool_call_result_message = tool_call_result_message.model_copy(
                        update={"content": content}
                    )
                logger.info(
                    "MCP tool result received",
                    tool_name=tool_name,
                    tool_call_id=tool_call.id,
                    duration=get_time_duration(start_time),
                    content_length=len(content) if content else 0,
                    is_error=not success,
                    error_type=error_type,
                    content=content[:200] + "..." + content[-200:]
                    if len(content) > 400
                    else content,
                )
                if tool_span is not None:
                    try:
                        tool_span.update(
                            output=content,
                            metadata={
                                "tool_name": tool_name,
                                "server_name": server_name,
                                "iteration": current_iteration + 1,
                                "tool_call_id": tool_call.id,
                                "conversation_id": self.current_conversation_id,
                                "user_id": self.current_user_id,
                                "is_error": not success,
                                **outcome_meta,
                            },
                            tags=[f"server:{server_name}"],
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to update tool observation span",
                            tool_name=tool_name,
                            error=exc,
                            error_type=type(exc).__name__,
                        )
                self._score_tool_success(
                    tool_span,
                    success=success,
                    error_type=error_type,
                    metadata_extra=outcome_meta or None,
                )
                return tool_call_result_message
            except Exception as exc:
                error_content, error_type = self._format_tool_exception(exc)
                try:
                    failed_arguments = json.loads(tool_call.function.arguments)
                    if not isinstance(failed_arguments, dict):
                        failed_arguments = {}
                except (json.JSONDecodeError, TypeError):
                    failed_arguments = {}
                guardrail_suffix = self.guardrail.record_outcome(
                    tool_name=tool_name,
                    arguments=failed_arguments,
                    success=False,
                    content=error_content,
                )
                if guardrail_suffix:
                    error_content = error_content + guardrail_suffix
                tool_call_result_message = ToolResultMessage(
                    role="tool",
                    is_error=True,
                    content=error_content,
                    tool_call_id=tool_call.id,
                )
                logger.error(
                    "Failed to call tool",
                    error=exc,
                    tool_name=tool_name,
                    iteration=current_iteration + 1,
                    tool_call_id=tool_call.id,
                    duration=get_time_duration(start_time),
                    content_length=len(error_content),
                    error_type=error_type,
                )
                mark_observation_error(tool_span, exc)
                if tool_span is not None:
                    with contextlib.suppress(Exception):
                        tool_span.update(output=error_content)
                self._score_tool_success(
                    tool_span,
                    success=False,
                    error_type=error_type,
                )
                return tool_call_result_message

    @staticmethod
    def _format_tool_exception(exc: BaseException) -> tuple[str, str]:
        """将工具异常归一化为 (content, error_type)。"""
        if ToolExecutor._is_timeout_error(exc):
            return (
                "⏱️ 工具调用超时，请稍后重试或换一种方式完成任务。",
                "timeout",
            )
        if isinstance(exc, ToolArgumentValidationError):
            return str(exc), "argument_validation_error"
        return str(exc) or type(exc).__name__, type(exc).__name__

    @staticmethod
    def _is_timeout_error(exc: BaseException) -> bool:
        """识别 TimeoutError、httpx 超时，以及 MCP/包装层带 timed out 语义的异常。"""
        timeout_type_names = {
            "TimeoutException",
            "ReadTimeout",
            "WriteTimeout",
            "ConnectTimeout",
            "PoolTimeout",
        }
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, TimeoutError):
                return True
            if type(current).__name__ in timeout_type_names:
                return True
            message = str(current).lower()
            if "timed out" in message or "timeout exceeded" in message:
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _resolve_tool_outcome(
        *,
        server_name: str | None,
        content: str,
        structured_content: dict[str, Any] | None,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """按 server 语义判定工具是否成功。

        shell / code 以退出码为准；其它 server 仍以空结果为失败。
        返回 ``(success, error_type, metadata)``。
        """
        if server_name == SHELL_SERVER:
            return ToolExecutor._resolve_shell_outcome(content, structured_content)
        if server_name == CODE_SERVER:
            return ToolExecutor._resolve_code_outcome(content, structured_content)
        if not content:
            return False, "empty_result", {}
        return True, None, {}

    @staticmethod
    def _resolve_shell_outcome(
        content: str,
        structured_content: dict[str, Any] | None,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        if structured_content is not None:
            meta: dict[str, Any] = {}
            exit_code = structured_content.get("exit_code")
            if exit_code is not None:
                meta["exit_code"] = exit_code
            if structured_content.get("blocked"):
                return False, "blocked", meta
            if structured_content.get("timed_out"):
                return False, "timed_out", meta
            if exit_code is None:
                return False, "missing_exit_code", meta
            if exit_code != 0:
                return False, "non_zero_exit", meta
            return True, None, meta

        lowered = content.lower()
        if content.startswith("Error:") or "command blocked" in lowered:
            error_type = "blocked" if "blocked" in lowered else "execution_error"
            return False, error_type, {}
        if not content:
            return False, "empty_result", {}
        return True, None, {}

    @staticmethod
    def _resolve_code_outcome(
        content: str,
        structured_content: dict[str, Any] | None,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        if structured_content is not None:
            meta: dict[str, Any] = {}
            compile_stage = structured_content.get("compile")
            if isinstance(compile_stage, dict):
                compile_code = compile_stage.get("code")
                if compile_code is not None:
                    meta["compile_code"] = compile_code
                if compile_code is not None and compile_code != 0:
                    return False, "compile_failed", meta

            run_stage = structured_content.get("run")
            if not isinstance(run_stage, dict):
                return False, "missing_run_stage", meta
            run_code = run_stage.get("code")
            if run_code is not None:
                meta["exit_code"] = run_code
            if run_stage.get("signal"):
                meta["signal"] = run_stage.get("signal")
                return False, "signal", meta
            if run_code is None:
                return False, "missing_exit_code", meta
            if run_code != 0:
                return False, "non_zero_exit", meta
            return True, None, meta

        if not content:
            return False, "empty_result", {}
        return True, None, {}

    @staticmethod
    def _score_tool_success(
        tool_span: Any,
        *,
        success: bool,
        error_type: str | None,
        metadata_extra: dict[str, Any] | None = None,
    ) -> None:
        """在 tool observation 上写入 BOOLEAN score ``tool_success``。"""
        metadata: dict[str, Any] | None = None
        if error_type or metadata_extra:
            metadata = {}
            if error_type:
                metadata["error_type"] = error_type
            if metadata_extra:
                metadata.update(metadata_extra)
        score_observation(
            tool_span,
            name="tool_success",
            value=success,
            data_type="BOOLEAN",
            comment=error_type,
            metadata=metadata,
        )

    async def _apply_tavily_compaction(
        self,
        *,
        tool_name: str,
        structured_content: dict[str, Any],
        tool_call_result_message: ToolResultMessage,
    ) -> ToolResultMessage:
        processor = TavilyResultProcessor(
            compactor=self.compactor,
            user_query=self.current_user_message,
            tolerance_tokens_count=self.tool_result_compression.tolerance_tokens,
            threshold_tokens_count=self.tool_result_compression.threshold_tokens,
        )
        compaction = await processor.format_result(tool_name, structured_content)
        return tool_call_result_message.model_copy(
            update=compaction.model_dump(mode="json")
        )

    async def _compact_tool_result_if_needed(
        self, tool_message: ToolResultMessage
    ) -> ToolResultMessage:
        content = tool_message.content or ""
        if not content:
            return tool_message
        compaction = await self.compactor.compact_markdown_tool_result(
            query=self.current_user_message,
            content=content,
            tolerance_tokens_count=self.tool_result_compression.tolerance_tokens,
            threshold_tokens_count=self.tool_result_compression.threshold_tokens,
        )
        return tool_message.model_copy(update=compaction.model_dump(mode="json"))

    @staticmethod
    def _build_tool_warning_message(
        tool_name: str, call_warnings: list[dict[str, Any]] | list[str]
    ) -> str:
        if not call_warnings:
            return ""
        legacy_filtered_params = [
            item for item in call_warnings if isinstance(item, str)
        ]
        messages: list[str] = []
        if legacy_filtered_params:
            messages.append(
                f"⚠️ 警告：以下参数被忽略（工具 {tool_name} 不支持这些参数）："
                f"{', '.join(legacy_filtered_params)}。"
                "请勿在后续调用中使用这些参数。"
            )
        for warning in call_warnings:
            if not isinstance(warning, dict):
                continue
            if warning.get("code") == "unsupported_arguments_filtered":
                removed_params = warning.get("details", {}).get("removed_params", [])
                if removed_params:
                    messages.append(
                        f"⚠️ 警告：以下参数被忽略（工具 {tool_name} 不支持这些参数）："
                        f"{', '.join(removed_params)}。"
                        "请勿在后续调用中使用这些参数。"
                    )
                continue
            message = warning.get("message")
            if isinstance(message, str) and message:
                messages.append(f"⚠️ 提示：{message}")
        if not messages:
            return ""
        return "\n".join(messages) + "\n\n"

"""Tool execution helpers for MCP-backed tool calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from toolz import get

from app.agents.utils import TavilyResultProcessor
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.schemas.llm import ToolResultMessage
from app.utils.common import normalize_url
from app.utils.context_compactor import ContextCompactor
from app.utils.logger import conversation_id_var, logger, user_id_var
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator


class ToolExecutor:
    """Execute MCP tools and compact their results."""

    TAVILY_TOOL_NAME = "tavily-mcp"
    WEB_PAGES_EXTRACT = "web_pages_extract"
    FILE_MCP_SERVER_NAME = "file-mcp"
    SHELL_MCP_SERVER_NAME = "shell-mcp"

    def __init__(
        self, mcp_manager: MCPClientManager, user_message: str, model_name: str
    ) -> None:
        self.mcp_manager = mcp_manager
        self.current_user_message = user_message
        self.current_user_id: str | None = None
        self.current_workspace_id: str | None = None
        self.tool_result_compression = settings.chat_context.tool_result_compression
        self.compactor = ContextCompactor(
            embedding_model=settings.embedding_model,
            tool_result_compression_config=self.tool_result_compression,
        )
        self.token_calculator = TokenCalculator(model_name)
        self.token_threshold: int = self.token_calculator.get_compression_threshold(0.5)

    def reset_for_request(
        self,
        user_message: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        self.current_user_message = user_message
        self.current_user_id = user_id
        self.current_workspace_id = workspace_id

        # Set contextvars for tools to access
        if user_id:
            user_id_var.set(user_id)
        if workspace_id:
            conversation_id_var.set(workspace_id)

    async def execute_tool_calls_parallel(
        self,
        *,
        tool_calls: list[ChatCompletionMessageFunctionToolCall],
        current_iteration: int,
        iterations_by_tool: dict[str, int],
        extracted_urls: set[str],
        on_arguments_recorded: Callable[[str, dict[str, Any], str], None],
        on_urls_extracted: Callable[[set[str]], None],
    ) -> list[ToolResultMessage]:
        tasks = [
            self.execute_single_tool(
                tool_call=tool_call,
                current_iteration=current_iteration,
                iterations_by_tool=iterations_by_tool,
                extracted_urls=extracted_urls,
                on_arguments_recorded=on_arguments_recorded,
                on_urls_extracted=on_urls_extracted,
            )
            for tool_call in tool_calls
            if tool_call is not None
        ]
        return await asyncio.gather(*tasks)

    async def execute_single_tool(
        self,
        *,
        tool_call: ChatCompletionMessageFunctionToolCall,
        current_iteration: int,
        iterations_by_tool: dict[str, int],
        extracted_urls: set[str],
        on_arguments_recorded: Callable[[str, dict[str, Any], str], None],
        on_urls_extracted: Callable[[set[str]], None],
    ) -> ToolResultMessage:
        tool_name = tool_call.function.name
        start_time = get_current_time()
        if tool_name not in iterations_by_tool:
            logger.warning(
                "Tool not found in iterations tracking (unexpected), initializing as exhausted",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            iterations_by_tool[tool_name] = 0
        if iterations_by_tool[tool_name] <= 0:
            logger.info(
                "Tool max iterations reached, skipping",
                tool_name=tool_name,
                iteration=current_iteration + 1,
            )
            return ToolResultMessage(
                role="tool",
                is_error=True,
                tool_call_id=tool_call.id,
                content=f"Tool {tool_name} has hit max iterations, skipping",
            )

        iterations_by_tool[tool_name] -= 1
        try:
            arguments = json.loads(tool_call.function.arguments)
            if tool_name == self.WEB_PAGES_EXTRACT and (urls := get("urls", arguments)):
                normalized_urls = {normalize_url(url) for url in urls if url}
                new_urls = normalized_urls - extracted_urls
                if not new_urls:
                    logger.info(
                        "All URLs already extracted, skipping web_pages_extract",
                        urls=urls,
                        iteration=current_iteration + 1,
                    )
                    return ToolResultMessage(
                        role="tool",
                        is_error=False,
                        tool_call_id=tool_call.id,
                        content="⚠️ 提示：这些 URL 已经在之前的调用中提取过了。请检查历史工具调用结果，如果已获得足够信息，请停止继续调用工具，并直接给出最终回答。",
                    )
                on_urls_extracted(new_urls)
                arguments["urls"] = new_urls
                logger.info(
                    "Filtered URLs for web_pages_extract",
                    original_count=len(urls),
                    new_count=len(new_urls),
                    iteration=current_iteration + 1,
                )

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
            skip_compaction = server_name in (
                self.FILE_MCP_SERVER_NAME,
                self.SHELL_MCP_SERVER_NAME,
            )
            if skip_compaction:
                logger.info(
                    "Skipping tool result compaction for agent skills workspace tool",
                    tool_name=tool_name,
                    tool_call_id=tool_call.id,
                )
            elif (
                server_name == self.TAVILY_TOOL_NAME
                and result.structured_content is not None
            ):
                tool_call_result_message = await self._apply_tavily_compaction(
                    tool_name=tool_name,
                    structured_content=result.structured_content,
                    tool_call_result_message=tool_call_result_message,
                )
            else:
                tool_call_result_message = await self._compact_tool_result_if_needed(
                    tool_call_result_message
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
            logger.info(
                "MCP tool result received",
                tool_name=tool_name,
                tool_call_id=tool_call.id,
                duration=get_time_duration(start_time),
                content_length=len(content) if content else 0,
                content=content[:200] + "..." + content[-200:]
                if len(content) > 400
                else content,
            )
            return tool_call_result_message
        except Exception as exc:
            tool_call_result_message = ToolResultMessage(
                role="tool",
                is_error=True,
                content=str(exc),
                tool_call_id=tool_call.id,
            )
            logger.error(
                "Failed to call tool",
                error=exc,
                tool_name=tool_name,
                iteration=current_iteration + 1,
                tool_call_id=tool_call.id,
                duration=get_time_duration(start_time),
                content_length=len(str(exc)) if str(exc) else 0,
            )
            return tool_call_result_message

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

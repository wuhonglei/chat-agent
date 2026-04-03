"""History windowing and summary helpers for chat streaming."""

from __future__ import annotations

from typing import cast

from app.prompts import get_user_message_combine_tool_calls
from app.protocols.chat_messages import format_tool_call_messages_for_llm
from app.schemas.chat import ChatMessageItem, tool_messages_from_content_blocks
from app.schemas.config import ChatContextConfig
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.services.conversation import (
    ContextSummaryService,
    ConversationContextDbService,
)
from app.utils.history_truncate import truncate_history_by_rounds_and_tokens
from app.utils.logger import logger
from app.utils.message import filter_tool_call_messages
from app.utils.token import TokenCalculator


def _truncated_set_ids(truncated_messages: list[ChatMessageItem]) -> list[str]:
    """当前截断消息的 id 列表（稳定排序），用于写入 last_summarized_message_ids。"""
    return sorted(m.id for m in truncated_messages)


async def _run_window_out_summary_only(
    conversation_id: str,
    truncated_messages: list[ChatMessageItem] | None,
    summary_max_tokens: int,
    *,
    new_summary: str | None = None,
    truncated_set_ids: list[str] | None = None,
) -> str | None:
    if new_summary is not None and truncated_set_ids is not None:
        logger.info(
            "Running window-out summary upsert (incremental)",
            conversation_id=conversation_id,
        )
        try:
            with ConversationContextDbService() as ctx_svc:
                context = ctx_svc.upsert_conversation_context(
                    conversation_id,
                    summary_before_window=new_summary,
                    last_summarized_message_ids=truncated_set_ids,
                )
                return context.summary_before_window
        except Exception as exc:
            logger.warning(
                "Window-out summary upsert failed",
                conversation_id=conversation_id,
                error=exc,
            )
        return None

    if not truncated_messages:
        return None

    logger.info(
        "Running window-out summary (full)",
        conversation_id=conversation_id,
        truncated_messages_count=len(truncated_messages),
        summary_max_tokens=summary_max_tokens,
    )
    try:
        summary_svc = ContextSummaryService()
        summary = await summary_svc.summarize_truncated_messages(
            truncated_messages, max_tokens=summary_max_tokens
        )
        if summary:
            with ConversationContextDbService() as ctx_svc:
                context = ctx_svc.upsert_conversation_context(
                    conversation_id,
                    summary_before_window=summary,
                    last_summarized_message_ids=truncated_set_ids,
                )
                return context.summary_before_window
        return None
    except Exception as exc:
        logger.warning(
            "Window-out summary task failed",
            conversation_id=conversation_id,
            error=exc,
        )
        return None


class HistoryContextService:
    """Prepare history messages for the chat session agent."""

    def __init__(
        self,
        chat_context_config: ChatContextConfig,
        token_calculator: TokenCalculator,
    ) -> None:
        self.chat_context_config = chat_context_config
        self.history_window_config = chat_context_config.history_window
        self.window_out_summary_config = chat_context_config.window_out_summary
        self.token_calculator = token_calculator

    def process_history_messages(
        self, history_messages: list[ChatMessageItem]
    ) -> list[ChatMessageItem]:
        if not history_messages:
            return []

        threshold_tokens = self.chat_context_config.tool_result_compression.message_summary_threshold_tokens
        last_round_start = max(0, len(history_messages) - 2)
        flat: list[ChatMessageItem] = []

        for idx, msg in enumerate(history_messages):
            if msg.role == "user":
                flat.append(msg)
                continue
            if msg.role != "assistant":
                flat.append(msg)
                continue

            tool_messages = msg.tool_calls or tool_messages_from_content_blocks(
                msg.content_blocks
            )
            if not tool_messages:
                flat.append(msg)
                continue

            tool_calls_list: list[ToolMessage] = filter_tool_call_messages(
                tool_messages
            )
            if not tool_calls_list:
                flat.append(msg)
                continue

            is_latest_tool_round = idx >= last_round_start
            tool_calls: list[ToolMessage] = []
            for tool_message in tool_calls_list:
                if getattr(tool_message, "role", None) == "assistant":
                    tool_calls.append(cast(ToolUseMessage, tool_message))
                    continue

                tool_result = cast(ToolResultMessage, tool_message)
                if is_latest_tool_round:
                    tool_calls.append(tool_result)
                    continue

                if tool_result.summary and tool_result.summary.strip():
                    effective_content = tool_result.summary
                else:
                    content_tokens = self.token_calculator.count_tokens(
                        tool_result.content or ""
                    )
                    if content_tokens <= threshold_tokens:
                        effective_content = tool_result.content or ""
                    else:
                        effective_content = (
                            "[内容已截断] "
                            + self.token_calculator.truncate_text_to_tokens(
                                tool_result.content or "", threshold_tokens
                            )
                        )
                tool_calls.append(
                    tool_result.model_copy(update={"content": effective_content})
                )

            tool_items = format_tool_call_messages_for_llm(
                tool_calls, clear_reasoning_content=True
            )
            last_message = flat[-1] if flat else None
            if last_message and last_message.role == "user":
                last_message.content = get_user_message_combine_tool_calls(
                    last_message.content or "",
                    tool_items,
                )
            flat.append(msg)

        return flat

    async def prepare_history_messages(
        self,
        raw_history: list[ChatMessageItem],
        conversation_id: str,
    ) -> tuple[str | None, list[ChatMessageItem]]:
        history_messages, truncated_messages = truncate_history_by_rounds_and_tokens(
            raw_history,
            self.history_window_config.max_rounds,
            self.history_window_config.max_tokens,
            self.token_calculator,
        )

        window_out_summary = None
        if self.window_out_summary_config.enabled and truncated_messages:
            current_ids = _truncated_set_ids(truncated_messages)
            with ConversationContextDbService() as ctx_svc:
                ctx = ctx_svc.get_conversation_context(conversation_id)
                window_out_summary = ctx.summary_before_window if ctx else None
            last_ids: list[str] = (
                list(ctx.last_summarized_message_ids or []) if ctx else []
            )
            if sorted(current_ids) == sorted(last_ids):
                return window_out_summary, self.process_history_messages(
                    history_messages
                )

            delta_ids = set(current_ids) - set(last_ids)
            summary_max_tokens = self.window_out_summary_config.summary_max_tokens
            if (
                set(last_ids) <= set(current_ids)
                and delta_ids
                and ctx
                and (ctx.summary_before_window or "").strip()
            ):
                delta_messages = [
                    msg for msg in truncated_messages if msg.id in delta_ids
                ]
                summary_svc = ContextSummaryService()
                new_summary = await summary_svc.summarize_merge(
                    ctx.summary_before_window or "",
                    delta_messages,
                    max_tokens=summary_max_tokens,
                )
                if new_summary:
                    window_out_summary = await _run_window_out_summary_only(
                        conversation_id=conversation_id,
                        truncated_messages=None,
                        summary_max_tokens=summary_max_tokens,
                        new_summary=new_summary,
                        truncated_set_ids=current_ids,
                    )
            else:
                window_out_summary = await _run_window_out_summary_only(
                    conversation_id=conversation_id,
                    truncated_messages=truncated_messages,
                    summary_max_tokens=summary_max_tokens,
                    truncated_set_ids=current_ids,
                )

        return window_out_summary, self.process_history_messages(history_messages)

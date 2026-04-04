"""History windowing and summary helpers for chat streaming."""

from __future__ import annotations

from app.schemas.chat import ChatMessageItem, ContentBlock, ToolResultBlock
from app.schemas.config import ChatContextConfig
from app.services.conversation import (
    ContextSummaryService,
    ConversationContextDbService,
)
from app.utils.history_truncate import (
    split_history_by_rounds,
    truncate_in_window_by_round_tokens,
)
from app.utils.logger import logger
from app.utils.token import TokenCalculator


def _truncated_set_ids(truncated_messages: list[ChatMessageItem]) -> list[str]:
    """当前截断消息的 id 列表（稳定排序），用于写入 last_summarized_message_ids。"""
    return sorted(m.id for m in truncated_messages)


async def _persist_window_out_summary(
    conversation_id: str,
    summary: str,
    message_ids: list[str],
) -> str | None:
    logger.info(
        "Running window-out summary upsert",
        conversation_id=conversation_id,
    )
    try:
        with ConversationContextDbService() as ctx_svc:
            context = ctx_svc.upsert_conversation_context(
                conversation_id,
                summary_before_window=summary,
                last_summarized_message_ids=message_ids,
            )
            return context.summary_before_window
    except Exception as exc:
        logger.warning(
            "Window-out summary upsert failed",
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
        processed_messages: list[ChatMessageItem] = []

        for idx, msg in enumerate(history_messages):
            if msg.role != "assistant":
                processed_messages.append(msg)
                continue

            is_latest_tool_round = idx >= last_round_start
            new_blocks: list[ContentBlock] = []
            has_tool_result = False
            for block in msg.content_blocks:
                if not isinstance(block, ToolResultBlock):
                    new_blocks.append(block)
                    continue

                has_tool_result = True
                effective_content = block.content or ""
                if not is_latest_tool_round:
                    if block.summary and block.summary.strip():
                        effective_content = block.summary
                    else:
                        content_tokens = self.token_calculator.count_tokens(
                            effective_content
                        )
                        if content_tokens > threshold_tokens:
                            effective_content = (
                                "[内容已截断] "
                                + self.token_calculator.truncate_text_to_tokens(
                                    effective_content, threshold_tokens
                                )
                            )

                new_blocks.append(
                    block.model_copy(
                        update={
                            "content": effective_content,
                            "summary": None,
                            "structured_content_for_display": None,
                        }
                    )
                )

            if not has_tool_result:
                processed_messages.append(msg)
                continue

            processed_messages.append(
                msg.model_copy(update={"content_blocks": new_blocks})
            )

        return processed_messages

    async def prepare_history_messages(
        self,
        raw_history: list[ChatMessageItem],
        conversation_id: str,
    ) -> tuple[str | None, list[ChatMessageItem]]:
        _, in_window_messages = split_history_by_rounds(
            raw_history,
            self.history_window_config.max_rounds,
        )
        compressed_in_window = self.process_history_messages(
            in_window_messages)
        final_in_window = truncate_in_window_by_round_tokens(
            compressed_in_window,
            self.history_window_config.max_tokens,
            self.token_calculator,
        )
        final_kept_ids = {m.id for m in final_in_window}
        out_of_window_messages = [
            m for m in raw_history if m.id not in final_kept_ids]

        window_out_summary = None
        before_window_summary = None
        if self.window_out_summary_config.enabled and out_of_window_messages:
            current_ids = _truncated_set_ids(out_of_window_messages)
            current_id_set = set(current_ids)
            with ConversationContextDbService() as ctx_svc:
                ctx = ctx_svc.get_conversation_context(conversation_id)
                before_window_summary = ctx.summary_before_window if ctx else None
            last_ids: list[str] = (
                list(ctx.last_summarized_message_ids or []) if ctx else []
            )
            last_id_set = set(last_ids)
            if current_id_set == last_id_set:
                return before_window_summary, final_in_window

            delta_ids = current_id_set - last_id_set
            summary_max_tokens = self.window_out_summary_config.summary_max_tokens
            summary_to_persist: str | None = None
            summary_svc = ContextSummaryService()
            use_incremental_summary = (
                last_id_set <= current_id_set
                and bool(delta_ids)
                and ctx is not None
                and bool(before_window_summary)
            )
            messages_to_summarize = out_of_window_messages
            if use_incremental_summary:
                messages_to_summarize = [
                    msg for msg in out_of_window_messages if msg.id in delta_ids
                ]
            try:
                summary_to_persist = await summary_svc.summarize_merge(
                    before_window_summary,
                    messages_to_summarize,
                    max_tokens=summary_max_tokens,
                )
            except Exception as exc:
                logger.warning(
                    "Window-out summary task failed",
                    conversation_id=conversation_id,
                    error=exc,
                )

            if summary_to_persist:
                window_out_summary = await _persist_window_out_summary(
                    conversation_id=conversation_id,
                    summary=summary_to_persist,
                    message_ids=current_ids,
                )

        return window_out_summary, final_in_window

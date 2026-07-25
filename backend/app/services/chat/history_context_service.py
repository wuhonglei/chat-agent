"""History windowing and summary helpers for chat streaming."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.chat import (
    ChatMessage,
    ContentBlock,
    ToolResultBlock,
    ToolUseBlock,
)
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

_TOOL_ARG_TRUNCATION_SUFFIX = "...[truncated]"


def _truncated_set_ids(truncated_messages: list[ChatMessage]) -> list[str]:
    """当前截断消息的 id 列表（稳定排序），用于写入 last_summarized_message_ids。"""
    return sorted(m.id for m in truncated_messages)


def _truncate_tool_call_args_json(args: str, head_chars: int = 200) -> str:
    """Shrink long string values inside tool-call arguments JSON while
    preserving JSON validity.

    Aligned with hermes-agent ``_truncate_tool_call_args_json``: parse →
    recursively shrink string leaves → re-serialize. Invalid JSON is returned
    unchanged (raw slicing produced broken JSON and provider 400 loops).
    """
    try:
        parsed: Any = json.loads(args)
    except (json.JSONDecodeError, TypeError, ValueError):
        return args

    def _shrink(obj: Any) -> Any:
        if isinstance(obj, str):
            if len(obj) > head_chars:
                return obj[:head_chars] + _TOOL_ARG_TRUNCATION_SUFFIX
            return obj
        if isinstance(obj, dict):
            return {k: _shrink(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_shrink(v) for v in obj]
        return obj

    return json.dumps(_shrink(parsed), ensure_ascii=False)


def _truncate_tool_use_arguments(
    block: ToolUseBlock,
    *,
    max_chars: int,
    keep_chars: int,
) -> ToolUseBlock:
    """Truncate oversized tool_use arguments (hermes Pass-3 style).

    Gate on whole ``arguments_text`` length (``max_chars``); then shrink long
    string leaves to ``keep_chars`` inside parsed JSON.
    """
    arguments_text = block.arguments_text or ""
    if not arguments_text or len(arguments_text) <= max_chars:
        return block

    new_args_text = _truncate_tool_call_args_json(arguments_text, head_chars=keep_chars)
    if new_args_text == arguments_text:
        return block

    try:
        new_args_json: Any = json.loads(new_args_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        new_args_json = None

    return block.model_copy(
        update={
            "arguments_text": new_args_text,
            "arguments_json": new_args_json
            if isinstance(new_args_json, dict)
            else None,
        }
    )


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

    def compress_history_messages(
        self, history_messages: list[ChatMessage]
    ) -> list[ChatMessage]:
        if not history_messages:
            return []

        compression_cfg = self.chat_context_config.tool_result_compression
        threshold_tokens = compression_cfg.message_summary_threshold_tokens
        tool_arg_max_chars = compression_cfg.tool_arg_max_chars
        tool_arg_keep_chars = compression_cfg.tool_arg_keep_chars
        last_round_start = max(0, len(history_messages) - 2)
        processed_messages: list[ChatMessage] = []

        for idx, msg in enumerate(history_messages):
            if msg.role != "assistant":
                processed_messages.append(msg)
                continue

            is_latest_tool_round = idx >= last_round_start
            new_blocks: list[ContentBlock] = []
            blocks_changed = False

            for block in msg.content_blocks:
                if isinstance(block, ToolUseBlock):
                    if is_latest_tool_round:
                        new_blocks.append(block)
                        continue
                    truncated_use = _truncate_tool_use_arguments(
                        block,
                        max_chars=tool_arg_max_chars,
                        keep_chars=tool_arg_keep_chars,
                    )
                    if truncated_use is not block:
                        blocks_changed = True
                    new_blocks.append(truncated_use)
                    continue

                if not isinstance(block, ToolResultBlock):
                    new_blocks.append(block)
                    continue

                blocks_changed = True
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
                                self.token_calculator.truncate_text_to_tokens_head_tail(
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

            if not blocks_changed:
                processed_messages.append(msg)
                continue

            processed_messages.append(
                msg.model_copy(update={"content_blocks": new_blocks})
            )

        return processed_messages

    async def prepare_history_messages(
        self,
        raw_history: list[ChatMessage],
        conversation_id: str,
    ) -> tuple[str | None, list[ChatMessage]]:
        _, in_window_messages = split_history_by_rounds(
            raw_history,
            self.history_window_config.max_rounds,
        )
        compressed_window_messages = self.compress_history_messages(in_window_messages)
        history_max_tokens = int(
            self.token_calculator.context_limit * self.history_window_config.token_ratio
        )
        window_messages_after_truncation = truncate_in_window_by_round_tokens(
            compressed_window_messages,
            history_max_tokens,
            self.token_calculator,
        )
        final_kept_ids = {m.id for m in window_messages_after_truncation}
        out_of_window_messages = [m for m in raw_history if m.id not in final_kept_ids]

        window_out_summary = None
        stored_summary_before_window = None
        if self.window_out_summary_config.enabled and out_of_window_messages:
            current_ids = _truncated_set_ids(out_of_window_messages)
            current_id_set = set(current_ids)
            with ConversationContextDbService() as ctx_svc:
                ctx = ctx_svc.get_conversation_context(conversation_id)
                stored_summary_before_window = (
                    ctx.summary_before_window if ctx else None
                )
                last_ids: list[str] = (
                    list(ctx.last_summarized_message_ids or []) if ctx else []
                )
            last_id_set = set(last_ids)
            if current_id_set == last_id_set:
                return stored_summary_before_window, window_messages_after_truncation

            delta_ids = current_id_set - last_id_set
            summary_max_tokens = self.window_out_summary_config.summary_max_tokens
            summary_to_persist: str | None = None
            summary_svc = ContextSummaryService()
            use_incremental_summary = (
                last_id_set <= current_id_set
                and bool(delta_ids)
                and ctx is not None
                and bool(stored_summary_before_window)
            )
            messages_to_summarize = out_of_window_messages
            if use_incremental_summary:
                messages_to_summarize = [
                    msg for msg in out_of_window_messages if msg.id in delta_ids
                ]
            try:
                summary_to_persist = await summary_svc.summarize_merge(
                    stored_summary_before_window,
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

        return window_out_summary, window_messages_after_truncation

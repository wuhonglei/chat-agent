"""History windowing and summary helpers for unified context guard."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.chat import (
    ChatMessage,
    ContentBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.schemas.config import ChatContextConfig, UnifiedContextGuardConfig
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage
from app.services.conversation import (
    ContextSummaryService,
    ConversationContextDbService,
)
from app.utils.date import get_datetime_now
from app.utils.history_truncate import split_history_by_token_budget
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
    """Truncate oversized tool_use arguments (hermes Pass-3 style)."""
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


def head_tail_truncate_chars(text: str, head_chars: int, tail_chars: int) -> str:
    if head_chars < 0:
        head_chars = 0
    if tail_chars < 0:
        tail_chars = 0
    keep = head_chars + tail_chars
    if keep <= 0 or len(text) <= keep:
        return text
    marker = "\n...[中间已省略]...\n"
    return text[:head_chars] + marker + text[-tail_chars:]


# 兼容旧内部名
_head_tail_truncate_chars = head_tail_truncate_chars


def tool_round_compressible_end(
    messages: list[ToolMessage],
    keep_recent_groups: int,
) -> int:
    """Step 4 可压缩区间的右开下标。

    以「一次 ``ToolUseMessage`` + 其后连续 ``ToolResultMessage``」为一组；
    ``keep_recent_groups`` 保护最新若干组。孤立的连续 result 也自成一组。
    """
    if not messages:
        return 0
    if keep_recent_groups <= 0:
        return len(messages)

    group_ends: list[int] = []
    i = 0
    n = len(messages)
    while i < n:
        msg = messages[i]
        if isinstance(msg, ToolUseMessage):
            j = i + 1
            while j < n and isinstance(messages[j], ToolResultMessage):
                j += 1
            group_ends.append(j)
            i = j
        elif isinstance(msg, ToolResultMessage):
            j = i + 1
            while j < n and isinstance(messages[j], ToolResultMessage):
                j += 1
            group_ends.append(j)
            i = j
        else:
            raise TypeError(f"unexpected tool message type: {type(msg)}")

    if keep_recent_groups >= len(group_ends):
        return 0

    first_kept = len(group_ends) - keep_recent_groups
    return group_ends[first_kept - 1] if first_kept > 0 else 0


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
    """Compression / summary primitives for the unified context guard."""

    def __init__(
        self,
        chat_context_config: ChatContextConfig,
        token_calculator: TokenCalculator,
    ) -> None:
        self.chat_context_config = chat_context_config
        self.window_out_summary_config = chat_context_config.window_out_summary
        self.unified_guard = chat_context_config.unified_guard
        self.token_calculator = token_calculator

    def compress_history_tool_results(
        self, history_messages: list[ChatMessage]
    ) -> list[ChatMessage]:
        """Step 2: compress all history ToolResultBlocks; truncate all tool_use args.

        Returns the same list object when nothing was modified.
        """
        if not history_messages:
            return history_messages

        compression_cfg = self.chat_context_config.tool_result_compression
        threshold_tokens = compression_cfg.message_summary_threshold_tokens
        tool_arg_max_chars = compression_cfg.tool_arg_max_chars
        tool_arg_keep_chars = compression_cfg.tool_arg_keep_chars
        processed_messages: list[ChatMessage] = []
        any_changed = False

        for msg in history_messages:
            if msg.role != "assistant":
                processed_messages.append(msg)
                continue

            new_blocks: list[ContentBlock] = []
            blocks_changed = False

            for block in msg.content_blocks:
                if isinstance(block, ToolUseBlock):
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

            any_changed = True
            processed_messages.append(
                msg.model_copy(update={"content_blocks": new_blocks})
            )

        if not any_changed:
            return history_messages
        return processed_messages

    def compress_tool_round_messages(
        self,
        tool_round_messages: list[ToolMessage],
        *,
        keep_recent: int | None = None,
        threshold_chars: int | None = None,
        keep_head_chars: int | None = None,
        keep_tail_chars: int | None = None,
    ) -> bool:
        """Step 4: size-aware head-tail truncate older tool results in-place.

        Returns True if any message content was modified.
        """
        guard = self.unified_guard
        keep_recent = (
            keep_recent if keep_recent is not None else guard.keep_recent_tool_results
        )
        threshold_chars = (
            threshold_chars
            if threshold_chars is not None
            else guard.tool_result_compress_threshold_chars
        )
        keep_head_chars = (
            keep_head_chars
            if keep_head_chars is not None
            else guard.tool_result_compress_keep_head_chars
        )
        keep_tail_chars = (
            keep_tail_chars
            if keep_tail_chars is not None
            else guard.tool_result_compress_keep_tail_chars
        )

        if not tool_round_messages or keep_recent < 0:
            return False

        compressible_end = tool_round_compressible_end(tool_round_messages, keep_recent)
        if compressible_end <= 0:
            return False

        candidates: list[tuple[int, ToolResultMessage]] = []
        for i in range(compressible_end):
            msg = tool_round_messages[i]
            if (
                isinstance(msg, ToolResultMessage)
                and len(msg.content) > threshold_chars
            ):
                candidates.append((i, msg))

        if not candidates:
            return False

        candidates.sort(key=lambda item: len(item[1].content), reverse=True)
        changed = False
        for _, msg in candidates:
            truncated = head_tail_truncate_chars(
                msg.content, keep_head_chars, keep_tail_chars
            )
            if truncated != msg.content:
                msg.content = truncated
                changed = True
        return changed

    async def generate_window_out_summary(
        self,
        *,
        conversation_id: str,
        out_of_window_messages: list[ChatMessage],
        prior_summary: str | None,
    ) -> str | None:
        """Step 3: incremental window-out summary with anti-thrash."""
        if not self.window_out_summary_config.enabled or not out_of_window_messages:
            return prior_summary

        return await self._generate_summary_with_guard(
            conversation_id=conversation_id,
            out_of_window_messages=out_of_window_messages,
            prior_summary=prior_summary,
        )

    async def _generate_summary_with_guard(
        self,
        *,
        conversation_id: str,
        out_of_window_messages: list[ChatMessage],
        prior_summary: str | None,
    ) -> str | None:
        guard = self.unified_guard
        current_ids = _truncated_set_ids(out_of_window_messages)
        current_id_set = set(current_ids)

        with ConversationContextDbService() as ctx_svc:
            ctx = ctx_svc.get_conversation_context(conversation_id)
            stored_summary = (
                prior_summary
                if prior_summary is not None
                else (ctx.summary_before_window if ctx else None)
            )
            last_ids: list[str] = (
                list(ctx.last_summarized_message_ids or []) if ctx else []
            )
            failure_count = int(ctx.summary_failure_count or 0) if ctx else 0
            last_failure_at = ctx.last_summary_failure_at if ctx else None

        last_id_set = set(last_ids)
        if current_id_set == last_id_set and stored_summary:
            return stored_summary

        if failure_count >= guard.anti_thrash_failure_threshold and last_failure_at:
            elapsed = (get_datetime_now() - last_failure_at).total_seconds()
            if elapsed < guard.anti_thrash_recovery_seconds:
                logger.info(
                    "Summary blocked by anti-thrashing",
                    conversation_id=conversation_id,
                    remaining=guard.anti_thrash_recovery_seconds - elapsed,
                )
                return stored_summary
            with ConversationContextDbService() as ctx_svc:
                ctx_svc.reset_summary_failure_count(conversation_id)

        delta_ids = current_id_set - last_id_set
        summary_max_tokens = self.window_out_summary_config.summary_max_tokens
        summary_svc = ContextSummaryService()
        use_incremental_summary = (
            last_id_set <= current_id_set and bool(delta_ids) and bool(stored_summary)
        )
        messages_to_summarize = out_of_window_messages
        if use_incremental_summary:
            messages_to_summarize = [
                msg for msg in out_of_window_messages if msg.id in delta_ids
            ]

        try:
            summary_to_persist = await summary_svc.summarize_merge(
                stored_summary,
                messages_to_summarize,
                max_tokens=summary_max_tokens,
            )
        except Exception as exc:
            logger.warning(
                "Window-out summary task failed",
                conversation_id=conversation_id,
                error=exc,
            )
            with ConversationContextDbService() as ctx_svc:
                ctx_svc.increment_summary_failure_count(conversation_id)
            return stored_summary

        if not summary_to_persist:
            with ConversationContextDbService() as ctx_svc:
                ctx_svc.increment_summary_failure_count(conversation_id)
            return stored_summary

        with ConversationContextDbService() as ctx_svc:
            ctx_svc.reset_summary_failure_count(conversation_id)

        persisted = await _persist_window_out_summary(
            conversation_id=conversation_id,
            summary=summary_to_persist,
            message_ids=current_ids,
        )
        return persisted or summary_to_persist

    def split_by_remaining_budget(
        self,
        history_messages: list[ChatMessage],
        remaining_budget: int,
    ) -> tuple[list[ChatMessage], list[ChatMessage]]:
        """Split history into in-window / out-of-window by remaining token budget."""
        return split_history_by_token_budget(
            history_messages,
            remaining_budget,
            self.token_calculator,
        )

    def get_stored_window_summary(self, conversation_id: str) -> str | None:
        """Load persisted window-out summary without running compression."""
        with ConversationContextDbService() as ctx_svc:
            return ctx_svc.get_conversation_context_summary(conversation_id)

    @staticmethod
    def compute_context_threshold(
        context_limit: int,
        model_max_output_tokens: int,
        guard: UnifiedContextGuardConfig,
    ) -> int:
        reserved_output = min(model_max_output_tokens, guard.max_output_tokens)
        return max(0, context_limit - reserved_output - guard.buffer_tokens)

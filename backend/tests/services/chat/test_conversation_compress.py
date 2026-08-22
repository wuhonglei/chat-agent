"""会话手动全量压缩与 last_summarized_message_ids 语义测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.chat import ChatMessage, TextBlock
from app.schemas.config import ChatContextConfig, WindowOutSummaryConfig
from app.services.chat import history_context_service as hcs_module
from app.services.chat.history_context_service import (
    HistoryContextService,
    _union_summarized_ids,
)
from app.utils.token import TokenCalculator


def _calc() -> TokenCalculator:
    return TokenCalculator(model="gpt-4o", context_limit=128_000)


def _svc() -> HistoryContextService:
    return HistoryContextService(
        ChatContextConfig(
            window_out_summary=WindowOutSummaryConfig(
                enabled=True, summary_max_tokens=500
            )
        ),
        _calc(),
    )


def _msg(msg_id: str, text: str = "hello") -> ChatMessage:
    return ChatMessage(
        id=msg_id,
        conversation_id="conv",
        role="user" if msg_id.startswith("u") else "assistant",
        content_blocks=[TextBlock(id=f"{msg_id}-t", text=text)],
        status="done",
    )


def test_union_summarized_ids_stable_sorted() -> None:
    assert _union_summarized_ids(["b", "a"], ["c", "a"]) == ["a", "b", "c"]


def test_filter_summarized_history_skips_known_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = MagicMock()
    ctx.last_summarized_message_ids = ["u0", "a0"]
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = ctx
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    messages = [_msg("u0"), _msg("a0"), _msg("u1"), _msg("a1")]
    filtered = _svc().filter_summarized_history("conv", messages)
    assert [m.id for m in filtered] == ["u1", "a1"]


def test_filter_summarized_history_noop_without_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = None
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    messages = [_msg("u0"), _msg("a0")]
    filtered = _svc().filter_summarized_history("conv", messages)
    assert filtered is messages


@pytest.mark.asyncio
async def test_compact_full_conversation_persists_union_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = MagicMock()
    ctx.summary_before_window = None
    ctx.last_summarized_message_ids = None
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = ctx
    ctx_svc.upsert_conversation_context.return_value = MagicMock(
        summary_before_window="new summary"
    )
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    summary_svc = MagicMock()
    summary_svc.format_conversation_for_summary.return_value = "source text " * 20
    summary_svc.summarize_merge = AsyncMock(return_value="new summary")
    summary_svc.token_calculator = _calc()
    monkeypatch.setattr(hcs_module, "ContextSummaryService", lambda: summary_svc)

    messages = [_msg("u0", "q"), _msg("a0", "a")]
    result = await _svc().compact_full_conversation("conv", messages)

    assert result.summary == "new summary"
    assert result.summarized_message_count == 2
    assert result.tokens_before > 0
    assert result.tokens_after > 0
    summary_svc.summarize_merge.assert_awaited_once()
    ctx_svc.upsert_conversation_context.assert_called_once()
    call_kwargs = ctx_svc.upsert_conversation_context.call_args
    assert call_kwargs.kwargs["summary_before_window"] == "new summary"
    assert call_kwargs.kwargs["last_summarized_message_ids"] == ["a0", "u0"]


@pytest.mark.asyncio
async def test_compact_full_conversation_idempotent_when_already_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [_msg("u0"), _msg("a0")]
    ctx = MagicMock()
    ctx.summary_before_window = "existing summary"
    ctx.last_summarized_message_ids = ["a0", "u0"]
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = ctx
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    summary_svc = MagicMock()
    summary_svc.format_conversation_for_summary.return_value = "source"
    summary_svc.summarize_merge = AsyncMock()
    summary_svc.token_calculator = _calc()
    monkeypatch.setattr(hcs_module, "ContextSummaryService", lambda: summary_svc)

    result = await _svc().compact_full_conversation("conv", messages)
    assert result.summary == "existing summary"
    summary_svc.summarize_merge.assert_not_awaited()
    ctx_svc.upsert_conversation_context.assert_not_called()


@pytest.mark.asyncio
async def test_compact_full_conversation_rejects_empty() -> None:
    with pytest.raises(ValueError, match="没有可压缩"):
        await _svc().compact_full_conversation("conv", [])


@pytest.mark.asyncio
async def test_generate_summary_with_guard_unions_ids_and_merges_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """手动全量后 last_ids 更大；自动切窗只摘要 delta 且 UNION 写回。"""
    ctx = MagicMock()
    ctx.summary_before_window = "prior summary"
    ctx.last_summarized_message_ids = ["u0", "a0"]
    ctx.summary_failure_count = 0
    ctx.last_summary_failure_at = None
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = ctx
    ctx_svc.upsert_conversation_context.return_value = MagicMock(
        summary_before_window="merged summary"
    )
    ctx_svc.reset_summary_failure_count = MagicMock()
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    captured: dict[str, Any] = {}

    async def _fake_merge(
        prior: str | None, messages: list[ChatMessage], max_tokens: int
    ) -> str:
        captured["prior"] = prior
        captured["ids"] = [m.id for m in messages]
        captured["max_tokens"] = max_tokens
        return "merged summary"

    summary_svc = MagicMock()
    summary_svc.summarize_merge = _fake_merge
    monkeypatch.setattr(hcs_module, "ContextSummaryService", lambda: summary_svc)

    out_of_window = [_msg("u1", "new q"), _msg("a1", "new a")]
    result = await _svc()._generate_summary_with_guard(
        conversation_id="conv",
        out_of_window_messages=out_of_window,
        prior_summary="prior summary",
    )
    assert result == "merged summary"
    assert captured["prior"] == "prior summary"
    assert captured["ids"] == ["u1", "a1"]
    call_kwargs = ctx_svc.upsert_conversation_context.call_args.kwargs
    assert call_kwargs["last_summarized_message_ids"] == ["a0", "a1", "u0", "u1"]


@pytest.mark.asyncio
async def test_generate_summary_skips_when_current_subset_of_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = MagicMock()
    ctx.summary_before_window = "already"
    ctx.last_summarized_message_ids = ["u0", "a0", "u1", "a1"]
    ctx.summary_failure_count = 0
    ctx.last_summary_failure_at = None
    ctx_svc = MagicMock()
    ctx_svc.get_conversation_context.return_value = ctx
    ctx_svc.__enter__.return_value = ctx_svc
    ctx_svc.__exit__.return_value = None
    monkeypatch.setattr(hcs_module, "ConversationContextDbService", lambda: ctx_svc)

    summary_svc = MagicMock()
    summary_svc.summarize_merge = AsyncMock()
    monkeypatch.setattr(hcs_module, "ContextSummaryService", lambda: summary_svc)

    result = await _svc()._generate_summary_with_guard(
        conversation_id="conv",
        out_of_window_messages=[_msg("u1"), _msg("a1")],
        prior_summary=None,
    )
    assert result == "already"
    summary_svc.summarize_merge.assert_not_awaited()

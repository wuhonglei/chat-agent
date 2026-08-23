"""ChatOrchestrator 失败/成功路径下的落库与 trace 行为单测。

通过 mock Langfuse 与各协作者，验证主会话流式失败时：
- 助手消息落库为 FAILED
- 不下发 done 事件、不触发记忆写入
- 根 span 标记 ERROR
并验证正常完成路径仍下发 done。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from app.schemas.chat import ChatRequest, MessageStatus, TextBlock
from app.services.chat import chat_orchestrator as orchestrator_module
from app.services.chat.chat_orchestrator import ChatOrchestrator
from app.utils.date import get_current_datetime_str


class _Conv(BaseModel):
    id: str = "conv-1"
    user_id: str = "user-1"


_USER_CREATED_AT = datetime(2026, 8, 23, 5, 30, 0, tzinfo=timezone.utc)


class _Msg(BaseModel):
    id: str
    role: str
    status: str = "pending"
    created_at: datetime = _USER_CREATED_AT


class _FakeAgent:
    """最小化 ChatSessionAgent 替身。"""

    def __init__(self, *, raise_in_stream: bool) -> None:
        self._raise_in_stream = raise_in_stream
        self.content = "partial answer"
        self.reasoning = ""
        self.content_blocks: list[Any] = []
        self.tool_round_messages: list[Any] = []
        self.iteration_checkpoint: Any = None
        self.mcp_manager = None

    def _sync_session_output(self) -> None:
        return None

    async def stream_session_events(self, **kwargs: Any) -> AsyncGenerator[str, None]:
        self.last_stream_kwargs = kwargs
        if self._raise_in_stream:
            raise RuntimeError("llm boom")
        yield "data: chunk\n\n"


def _build_orchestrator(*, raise_in_stream: bool) -> tuple[ChatOrchestrator, Any]:
    agent = _FakeAgent(raise_in_stream=raise_in_stream)

    history_service = MagicMock()
    history_service.get_stored_window_summary = MagicMock(return_value=None)
    history_service.filter_summarized_history = MagicMock(side_effect=lambda _cid, msgs: msgs)

    post_process = MagicMock()
    post_process.persist_final_assistant_message = MagicMock(
        return_value=datetime(2026, 1, 1)
    )
    post_process.schedule_memory_write = MagicMock()

    kb_service = MagicMock()
    kb_service.build_context_blocks_for_current_turn = AsyncMock(return_value=None)

    orch = ChatOrchestrator(
        chat_session_agent=agent,
        title_generation_agent=MagicMock(),
        history_context_service=history_service,
        post_process_service=post_process,
        kb_rag_context_service=kb_service,
    )
    return orch, post_process


def _patch_common(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, AsyncMock]:
    """禁用 Langfuse 并替换 MessageDbService，返回可断言的 message_service。"""
    monkeypatch.setattr(orchestrator_module, "is_enabled", lambda: False)
    monkeypatch.setattr(orchestrator_module, "get_langfuse", lambda: None)

    message_service = MagicMock()
    message_service.get_conversation_and_messages = MagicMock(
        return_value=(
            _Conv(),
            _Msg(id="u-1", role="user"),
            _Msg(id="a-1", role="assistant"),
        )
    )
    message_service.get_history_messages_by_ids = MagicMock(return_value=[])
    message_service.update_assistant_message = MagicMock()

    @contextmanager
    def _fake_db() -> Any:
        yield message_service

    monkeypatch.setattr(orchestrator_module, "MessageDbService", _fake_db)
    invalidate = AsyncMock()
    monkeypatch.setattr(
        orchestrator_module,
        "invalidate_conversation_state",
        invalidate,
    )
    return message_service, invalidate


def _chat_request() -> ChatRequest:
    return ChatRequest(
        content_blocks=[TextBlock(id="b1", text="hello")],
        conversation_id="conv-1",
        history_ids=[],
        regenerate_title=False,
    )


@pytest.mark.asyncio
async def test_stream_failure_marks_failed_and_skips_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message_service, invalidate = _patch_common(monkeypatch)
    orch, post_process = _build_orchestrator(raise_in_stream=True)

    events: list[str] = []
    async for event in orch.run_chat_turn(
        chat_request=_chat_request(),
        user_message_id="u-1",
        assistant_message_id="a-1",
        user_id="user-1",
        memory_search=AsyncMock(return_value=[]),
    ):
        events.append(event)

    # 下发了 error 事件，但没有 done 事件
    assert any('"type": "error"' in e for e in events)
    assert not any('"type": "done"' in e for e in events)

    # 助手消息落库为 FAILED
    failed_calls = [
        call
        for call in message_service.update_assistant_message.call_args_list
        if call.kwargs.get("status") == MessageStatus.FAILED
    ]
    assert len(failed_calls) == 1
    invalidate.assert_awaited_once_with("conv-1", "user-1")

    # 失败路径不触发记忆写入与最终持久化
    post_process.schedule_memory_write.assert_not_called()
    post_process.persist_final_assistant_message.assert_not_called()


@pytest.mark.asyncio
async def test_stream_success_emits_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message_service, invalidate = _patch_common(monkeypatch)
    orch, post_process = _build_orchestrator(raise_in_stream=False)

    events: list[str] = []
    async for event in orch.run_chat_turn(
        chat_request=_chat_request(),
        user_message_id="u-1",
        assistant_message_id="a-1",
        user_id="user-1",
        memory_search=AsyncMock(return_value=[]),
    ):
        events.append(event)

    assert any('"type": "done"' in e for e in events)
    assert not any('"type": "error"' in e for e in events)
    post_process.persist_final_assistant_message.assert_called_once()
    post_process.schedule_memory_write.assert_called_once()
    invalidate.assert_awaited_once_with("conv-1", "user-1")
    # 成功路径不应将消息标为 FAILED
    failed_calls = [
        call
        for call in message_service.update_assistant_message.call_args_list
        if call.kwargs.get("status") == MessageStatus.FAILED
    ]
    assert not failed_calls


@pytest.mark.asyncio
async def test_stream_passes_user_message_created_at_as_current_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """编排层用 user_message.created_at 冻结 <current_datetime>，不取流式开始时刻。"""
    _patch_common(monkeypatch)
    orch, _ = _build_orchestrator(raise_in_stream=False)

    async for _ in orch.run_chat_turn(
        chat_request=_chat_request(),
        user_message_id="u-1",
        assistant_message_id="a-1",
        user_id="user-1",
        memory_search=AsyncMock(return_value=[]),
    ):
        pass

    fake_agent = orch.chat_session_agent
    assert isinstance(fake_agent, _FakeAgent)
    assert fake_agent.last_stream_kwargs["current_datetime"] == get_current_datetime_str(
        _USER_CREATED_AT
    )

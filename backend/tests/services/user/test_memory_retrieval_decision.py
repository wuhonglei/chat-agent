"""记忆检索规则闸门单测。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.config import ChatContextConfig, LLMConfig, MemoryConfig
from app.services.chat.chat_service import ChatService
from app.services.user.memory_retrieval_decision import (
    classify_memory_need,
    needs_memory,
)


@pytest.mark.parametrize(
    ("query", "expected", "reason"),
    [
        ("hi", False, "short"),
        ("好的", False, "short"),  # len < 5 after strip
        ("什么是 OAuth2", False, "skip"),
        ("what is a vector database", False, "skip"),
        ("帮我写一个快速排序", False, "skip"),
        ("write a binary search", False, "skip"),
        ("翻译这段英文：Hello", False, "skip"),
        ("计算 1+1", False, "skip"),
        ("算一下 12 * 3", False, "skip"),
        ("我之前定的技术栈是什么？", True, "memory"),
        ("remember what I said last time", True, "memory"),
        ("根据我的偏好推荐餐厅", True, "memory"),
        ("recommend something for me", True, "memory"),
        ("please continue", True, "memory"),
        ("我喜欢吃什么", True, "memory"),
        # SKIP + MEMORY 同时命中 → 需要记忆
        ("帮我写一个符合我的风格的脚本", True, "memory"),
        ("什么是我之前说的方案", True, "memory"),
        # 未命中任何模式 → 默认检索
        ("深圳明天天气怎么样", True, "default"),
        ("今天股市开盘了吗", True, "default"),
    ],
)
def test_needs_memory_table(
    query: str, expected: bool, reason: str
) -> None:
    assert needs_memory(query) is expected
    needed, hit_reason = classify_memory_need(query)
    assert needed is expected
    assert hit_reason == reason


def _make_chat_service(
    *,
    retrieval_decision_enabled: bool = True,
) -> ChatService:
    llm_config = LLMConfig(
        api_key="sk-test",
        api_base="https://example.com/v1",
        model_name="test-model",
        context_limit=128000,
        max_output_tokens=4096,
        title="test",
        description="test",
    )
    chat_context = ChatContextConfig(
        memory_config=MemoryConfig(
            base_url="http://127.0.0.1:8888",
            api_key="oss-key",
            retrieval_decision_enabled=retrieval_decision_enabled,
        )
    )
    mcp_manager = MagicMock()
    return ChatService(
        think_mode=False,
        llm_config=llm_config,
        mcp_manager=mcp_manager,
        chat_context_config=chat_context,
    )


@pytest.mark.asyncio
async def test_search_skips_mem0_when_rules_say_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_chat_service()
    search_mock = AsyncMock(return_value=[{"id": "m1"}])
    monkeypatch.setattr(service.memory_service, "search", search_mock)

    result = await service._search_user_memories(
        query="什么是 OAuth2",
        user_id="u1",
    )

    assert result == []
    search_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_calls_mem0_when_rules_say_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_chat_service()
    memory = MagicMock()
    memory.id = "m1"
    memory.memory = "喜欢喝茶"
    memory.hash = "h1"
    memory.metadata = None
    memory.created_at = "2026-01-01T00:00:00Z"
    memory.score = 0.9
    search_mock = AsyncMock(return_value=[memory])
    monkeypatch.setattr(service.memory_service, "search", search_mock)

    result = await service._search_user_memories(
        query="我之前喜欢喝什么",
        user_id="u1",
    )

    assert len(result) == 1
    assert result[0].memory == "喜欢喝茶"
    search_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_bypasses_rules_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_chat_service(retrieval_decision_enabled=False)
    memory = MagicMock()
    memory.id = "m1"
    memory.memory = "无关记忆"
    memory.hash = "h1"
    memory.metadata = None
    memory.created_at = "2026-01-01T00:00:00Z"
    memory.score = 0.5
    search_mock = AsyncMock(return_value=[memory])
    monkeypatch.setattr(service.memory_service, "search", search_mock)

    # 知识问答在规则开启时会跳过；关闭后仍应 search
    result = await service._search_user_memories(
        query="什么是 OAuth2",
        user_id="u1",
    )

    assert len(result) == 1
    search_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_short_ack_skips_via_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_chat_service()
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(service.memory_service, "search", search_mock)

    result = await service._search_user_memories(query="好的", user_id="u1")

    assert result == []
    search_mock.assert_not_awaited()


def test_memory_config_default_enables_retrieval_decision() -> None:
    cfg = MemoryConfig()
    assert cfg.retrieval_decision_enabled is True

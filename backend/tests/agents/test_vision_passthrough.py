"""Vision passthrough routing in the tool executor."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.agents.tool_executor import ToolExecutor
from app.agents.utils.content_blocks import ContentBlocksAggregator
from app.mcp.constants import VISION_SERVER
from app.mcp.mcp_servers.vision_mcp.analyze import (
    build_vision_llm_content,
    vision_passthrough_stub,
)
from app.schemas.llm import ToolResultMessage


class _FakeMCPManager:
    def get_server_for_tool(self, tool_name: str) -> str | None:
        return None


def _executor(*, image_support: bool) -> ToolExecutor:
    return ToolExecutor(
        cast(Any, _FakeMCPManager()),
        "message",
        "gpt-4o-mini",
        131072,
        image_support=image_support,
    )


def _loaded_image(question: str = "颜色") -> tuple[SimpleNamespace, ToolResultMessage]:
    data_url = "data:image/png;base64,AAAA"
    result = SimpleNamespace(
        structured_content={
            "kind": "vision_passthrough",
            "data_url": data_url,
            "question": question,
        },
        is_error=False,
    )
    message = ToolResultMessage(
        role="tool",
        tool_call_id="c1",
        is_error=False,
        content=vision_passthrough_stub(question),
    )
    return result, message


@pytest.mark.asyncio
async def test_image_support_attaches_image_without_vision_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_ask(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("vision model should not be called")

    monkeypatch.setattr("app.agents.tool_executor.ask_vision_model", fail_ask)
    result, message = _loaded_image()
    resolved = await _executor(image_support=True)._resolve_vision_passthrough(
        server_name=VISION_SERVER,
        result=result,
        message=message,
    )

    assert "base64" not in resolved.content
    assert resolved.content == vision_passthrough_stub("颜色")
    assert resolved.llm_content == build_vision_llm_content(
        "data:image/png;base64,AAAA",
        "颜色",
    )
    assert resolved.llm_content[1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )


@pytest.mark.asyncio
async def test_text_model_uses_vision_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    async def fake_ask(question: str, data_url: str) -> str:
        seen.append((question, data_url))
        return "图中是红色方块"

    monkeypatch.setattr("app.agents.tool_executor.ask_vision_model", fake_ask)
    result, message = _loaded_image("这是什么")
    resolved = await _executor(image_support=False)._resolve_vision_passthrough(
        server_name=VISION_SERVER,
        result=result,
        message=message,
    )

    assert seen == [("这是什么", "data:image/png;base64,AAAA")]
    assert resolved.content == "图中是红色方块"
    assert resolved.llm_content is None
    assert "base64" not in resolved.content


@pytest.mark.asyncio
async def test_empty_vision_answer_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def empty_ask(*_args: Any, **_kwargs: Any) -> str:
        return "  "

    monkeypatch.setattr("app.agents.tool_executor.ask_vision_model", empty_ask)
    result, message = _loaded_image()
    with pytest.raises(ValueError, match="empty content"):
        await _executor(image_support=False)._resolve_vision_passthrough(
            server_name=VISION_SERVER,
            result=result,
            message=message,
        )


@pytest.mark.asyncio
async def test_passthrough_skips_compaction() -> None:
    executor = _executor(image_support=True)
    result, message = _loaded_image()
    message = message.model_copy(
        update={
            "llm_content": build_vision_llm_content(
                "data:image/png;base64,AAAA",
                "颜色",
            )
        }
    )

    async def fail_compact(_tool_message: ToolResultMessage) -> ToolResultMessage:
        raise AssertionError("compaction should be skipped")

    executor._compact_tool_result_if_needed = fail_compact  # type: ignore[method-assign]
    shaped = await executor._soft_shape_tool_result(
        tool_name="vision_analyze",
        tool_call_id="c1",
        server_name=VISION_SERVER,
        result=result,
        message=message,
    )
    assert shaped.llm_content == message.llm_content
    assert shaped.content == message.content


def test_persisted_tool_block_keeps_stub_without_image() -> None:
    aggregator = ContentBlocksAggregator()
    data_url = "data:image/png;base64,AAAA"
    stub = vision_passthrough_stub("颜色")
    event = aggregator.append_tool_result(
        ToolResultMessage(
            role="tool",
            tool_call_id="c1",
            is_error=False,
            content=stub,
            llm_content=build_vision_llm_content(data_url, "颜色"),
        )
    )
    block = event["block"]
    assert block["content"] == stub
    assert "base64" not in block["content"]
    assert "llm_content" not in block

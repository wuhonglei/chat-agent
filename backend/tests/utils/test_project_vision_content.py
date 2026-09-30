"""Provider projection and token counting for vision tool results."""

from __future__ import annotations

from app.mcp.mcp_servers.vision_mcp.analyze import build_vision_llm_content
from app.protocols.chat_messages import format_tool_call_messages_for_llm
from app.schemas.llm import ToolResultMessage
from app.utils.message import project_messages_for_provider
from app.utils.token import TokenCalculator

_DATA_URL = "data:image/png;base64," + ("A" * 400)
_STUB = "图片已交给当前模型直接查看。问题：颜色"


def _tool_result() -> ToolResultMessage:
    return ToolResultMessage(
        role="tool",
        tool_call_id="c1",
        is_error=False,
        content=_STUB,
        llm_content=build_vision_llm_content(_DATA_URL, "颜色"),
    )


def _tool_message() -> dict[str, object]:
    formatted = format_tool_call_messages_for_llm([_tool_result()])
    return formatted[0]


def test_project_replaces_tool_content_with_image_parts() -> None:
    projected = project_messages_for_provider(
        [
            _tool_message(),
            {
                "role": "tool",
                "tool_call_id": "c2",
                "content": "普通文本结果",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看这张图"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,BBBB"},
                    },
                ],
                "source": {"kind": "user"},
            },
        ]
    )

    tool_parts = projected[0]["content"]
    assert isinstance(tool_parts, list)
    assert tool_parts[0]["type"] == "text"
    assert "不要编造图中不存在的内容" in tool_parts[0]["text"]
    assert tool_parts[0]["text"].endswith("颜色")
    assert tool_parts[1] == {
        "type": "image_url",
        "image_url": {"url": _DATA_URL},
    }
    assert "llm_content" not in projected[0]
    assert projected[1]["content"] == "普通文本结果"
    assert "source" not in projected[2]
    assert (
        projected[2]["content"][1]["image_url"]["url"] == "data:image/png;base64,BBBB"
    )


def test_project_drops_unknown_multimodal_parts() -> None:
    projected = project_messages_for_provider(
        [
            {
                "role": "tool",
                "tool_call_id": "c1",
                "content": _STUB,
                "llm_content": [
                    {"type": "text", "text": "看图"},
                    {"type": "input_audio", "audio": "nope"},
                    {"type": "image_url", "image_url": {"url": _DATA_URL}},
                ],
            }
        ]
    )
    parts = projected[0]["content"]
    assert [part["type"] for part in parts] == ["text", "image_url"]


def test_projected_token_count_includes_image_part() -> None:
    formatted = _tool_message()
    calculator = TokenCalculator(model="gpt-4o", context_limit=8192)
    stub_tokens = calculator.count_messages_tokens([formatted])
    wire_tokens = calculator.count_messages_tokens(
        project_messages_for_provider([formatted])
    )
    assert wire_tokens > stub_tokens

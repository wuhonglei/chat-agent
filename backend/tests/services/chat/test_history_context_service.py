"""HistoryContextService.compress_history_tool_results 单元测试。"""

from __future__ import annotations

import json

from app.schemas.chat import (
    ChatMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from app.schemas.config import ChatContextConfig, ToolResultCompressionConfig
from app.services.chat.history_context_service import HistoryContextService
from app.utils.token import TokenCalculator


def _calculator() -> TokenCalculator:
    return TokenCalculator(model="gpt-4o", context_limit=128_000)


def _service(
    *,
    message_summary_threshold_tokens: int = 50,
    tool_arg_max_chars: int = 500,
    tool_arg_keep_chars: int = 200,
) -> HistoryContextService:
    config = ChatContextConfig(
        tool_result_compression=ToolResultCompressionConfig(
            message_summary_threshold_tokens=message_summary_threshold_tokens,
            tool_arg_max_chars=tool_arg_max_chars,
            tool_arg_keep_chars=tool_arg_keep_chars,
        )
    )
    return HistoryContextService(config, _calculator())


def _user(msg_id: str) -> ChatMessage:
    return ChatMessage(
        id=msg_id,
        conversation_id="conv",
        role="user",
        content_blocks=[TextBlock(id=f"{msg_id}-t", text="hi")],
        status="done",
    )


def _tool_use(
    *,
    block_id: str,
    tool_call_id: str,
    arguments: dict[str, object] | str,
) -> ToolUseBlock:
    if isinstance(arguments, str):
        arguments_text = arguments
        arguments_json = None
    else:
        arguments_text = json.dumps(arguments, ensure_ascii=False)
        arguments_json = arguments
    return ToolUseBlock(
        id=block_id,
        tool_call_id=tool_call_id,
        name="file_write_file",
        server_name="file",
        mcp_tool_name="write_file",
        arguments_text=arguments_text,
        arguments_json=arguments_json if isinstance(arguments, dict) else None,
    )


def _tool_result(
    *,
    block_id: str,
    tool_call_id: str,
    tool_use_id: str,
    content: str,
    summary: str | None = None,
) -> ToolResultBlock:
    return ToolResultBlock(
        id=block_id,
        tool_call_id=tool_call_id,
        tool_use_id=tool_use_id,
        content=content,
        summary=summary,
    )


def _assistant_with_tools(
    msg_id: str,
    blocks: list[ToolUseBlock | ToolResultBlock | TextBlock],
) -> ChatMessage:
    return ChatMessage(
        id=msg_id,
        conversation_id="conv",
        role="assistant",
        content_blocks=list(blocks),
        status="done",
    )


def test_all_history_tool_use_args_truncated_and_tool_results_compressed() -> None:
    """Step 2：所有历史 ToolResult 可压；所有轮 tool_use args 均可截断。"""
    large_content = "RESULT_" + ("x" * 4000)
    large_code = "a" * 2000
    older = _assistant_with_tools(
        "a1",
        [
            _tool_use(
                block_id="u1",
                tool_call_id="call_1",
                arguments={"path": "a.py", "content": large_code},
            ),
            _tool_result(
                block_id="r1",
                tool_call_id="call_1",
                tool_use_id="u1",
                content=large_content,
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [
            _tool_use(
                block_id="u2",
                tool_call_id="call_2",
                arguments={"path": "b.py", "content": large_code},
            ),
            _tool_result(
                block_id="r2",
                tool_call_id="call_2",
                tool_use_id="u2",
                content=large_content,
                summary="latest summary",
            ),
        ],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    out = _service(
        tool_arg_max_chars=500, tool_arg_keep_chars=200
    ).compress_history_tool_results(history)

    latest_out = out[3]
    use_block = latest_out.content_blocks[0]
    result_block = latest_out.content_blocks[1]
    assert isinstance(use_block, ToolUseBlock)
    assert isinstance(result_block, ToolResultBlock)
    args = json.loads(use_block.arguments_text)
    assert args["path"] == "b.py"
    assert args["content"] == ("a" * 200) + "...[truncated]"
    assert result_block.content == "latest summary"
    assert result_block.summary is None


def test_older_round_prefers_summary_for_tool_result() -> None:
    older = _assistant_with_tools(
        "a1",
        [
            _tool_result(
                block_id="r1",
                tool_call_id="call_1",
                tool_use_id="u1",
                content="x" * 5000,
                summary="short summary",
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [TextBlock(id="t2", text="done")],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    out = _service().compress_history_tool_results(history)
    result_block = out[1].content_blocks[0]
    assert isinstance(result_block, ToolResultBlock)
    assert result_block.content == "short summary"
    assert result_block.summary is None


def test_older_round_head_tail_truncates_large_tool_result() -> None:
    # 构造明显超过 threshold 的内容：头部与尾部可区分
    content = ("HEAD" * 200) + ("MID" * 2000) + ("TAIL" * 200)
    older = _assistant_with_tools(
        "a1",
        [
            _tool_result(
                block_id="r1",
                tool_call_id="call_1",
                tool_use_id="u1",
                content=content,
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [TextBlock(id="t2", text="done")],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    calc = _calculator()
    svc = _service(message_summary_threshold_tokens=80)
    out = svc.compress_history_tool_results(history)
    result_block = out[1].content_blocks[0]
    assert isinstance(result_block, ToolResultBlock)
    assert "中间已省略" in result_block.content
    assert result_block.content.startswith("HEAD")
    assert (
        result_block.content.rstrip().endswith("TAIL")
        or "TAIL" in result_block.content[-40:]
    )
    assert calc.count_tokens(result_block.content) <= 80


def test_older_round_truncates_large_tool_use_string_args() -> None:
    large_code = "c" * 1200
    older = _assistant_with_tools(
        "a1",
        [
            _tool_use(
                block_id="u1",
                tool_call_id="call_1",
                arguments={"path": "a.py", "content": large_code},
            ),
            _tool_result(
                block_id="r1",
                tool_call_id="call_1",
                tool_use_id="u1",
                content="ok",
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [TextBlock(id="t2", text="done")],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    out = _service(
        tool_arg_max_chars=500, tool_arg_keep_chars=200
    ).compress_history_tool_results(history)

    use_block = out[1].content_blocks[0]
    assert isinstance(use_block, ToolUseBlock)
    args = json.loads(use_block.arguments_text)
    assert args["path"] == "a.py"
    assert args["content"] == ("c" * 200) + "...[truncated]"
    assert use_block.arguments_json == args


def test_older_round_invalid_json_tool_args_passthrough() -> None:
    """hermes: 非法 JSON 原样保留，禁止对 raw 字符串切片（避免 provider 400）。"""
    invalid_args = "{not-json " + ("z" * 2500)
    older = _assistant_with_tools(
        "a1",
        [
            _tool_use(
                block_id="u1",
                tool_call_id="call_1",
                arguments=invalid_args,
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [TextBlock(id="t2", text="done")],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    out = _service(tool_arg_keep_chars=200).compress_history_tool_results(history)
    use_block = out[1].content_blocks[0]
    assert isinstance(use_block, ToolUseBlock)
    assert use_block.arguments_text == invalid_args


def test_older_round_nested_tool_args_are_walked() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "x" * 500},
            {"role": "assistant", "content": "ok"},
        ],
        "meta": {"note": "y" * 500},
    }
    older = _assistant_with_tools(
        "a1",
        [
            _tool_use(
                block_id="u1",
                tool_call_id="call_1",
                arguments=payload,
            ),
        ],
    )
    latest = _assistant_with_tools(
        "a2",
        [TextBlock(id="t2", text="done")],
    )
    history = [_user("u1"), older, _user("u2"), latest]
    out = _service(
        tool_arg_max_chars=500, tool_arg_keep_chars=200
    ).compress_history_tool_results(history)
    use_block = out[1].content_blocks[0]
    assert isinstance(use_block, ToolUseBlock)
    parsed = json.loads(use_block.arguments_text)
    assert parsed["messages"][0]["content"] == ("x" * 200) + "...[truncated]"
    assert parsed["messages"][1]["content"] == "ok"
    assert parsed["meta"]["note"] == ("y" * 200) + "...[truncated]"


def test_truncate_text_to_tokens_head_tail_helper() -> None:
    calc = _calculator()
    text = ("A" * 400) + ("B" * 400) + ("C" * 400)
    out = calc.truncate_text_to_tokens_head_tail(text, max_tokens=40)
    assert "中间已省略" in out
    assert out.startswith("A")
    assert "C" in out[-20:]
    assert calc.count_tokens(out) <= 40

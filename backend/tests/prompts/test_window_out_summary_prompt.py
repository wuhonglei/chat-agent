"""窗口外摘要 prompt 模板与序列化单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.prompts.prompt_utils import (
    get_system_prompt_for_chat_session,
    get_user_message_for_tool_calls,
    get_window_out_summary_compress_prompt,
    get_window_out_summary_merge_prompt,
)
from app.schemas.chat import ChatMessage, TextBlock, ToolResultBlock, ToolUseBlock
from app.services.conversation.context_summary_service import ContextSummaryService


REQUIRED_SECTIONS = (
    "## 用户核心需求",
    "## 活跃任务",
    "## 已完成工作",
    "## 进行中任务",
    "## 待处理需求",
    "## 错误与修复",
    "## 关键决策",
    "## 关键上下文",
    "## 下一步",
)


def test_merge_prompt_without_prior_summary_has_structure() -> None:
    prompt = get_window_out_summary_merge_prompt(
        prior_summary="",
        new_messages_text="[user]: 请修复登录 bug",
        max_tokens=1000,
    )
    assert "<prior_summary>" not in prompt
    assert "[user]: 请修复登录 bug" in prompt
    assert "约 1000 token" in prompt
    for section in REQUIRED_SECTIONS:
        assert section in prompt


def test_merge_prompt_with_prior_summary_includes_incremental_rules() -> None:
    prompt = get_window_out_summary_merge_prompt(
        prior_summary="## 用户核心需求\n- 旧目标",
        new_messages_text="[user]: 改用 JWT",
        max_tokens=800,
    )
    assert "<prior_summary>" in prompt
    assert "## 用户核心需求\n- 旧目标" in prompt
    assert "活跃任务" in prompt
    assert "保留仍成立的信息" in prompt
    assert "约 800 token" in prompt


def test_compress_prompt_keeps_same_sections() -> None:
    prompt = get_window_out_summary_compress_prompt(
        prior_summary="很长的旧摘要",
        max_tokens=500,
    )
    assert "很长的旧摘要" in prompt
    assert "约 500 token" in prompt
    for section in REQUIRED_SECTIONS:
        assert section in prompt


def test_window_out_summary_is_injected_into_system_prompt() -> None:
    prompt = get_system_prompt_for_chat_session(
        agent_mode=0,
        window_out_summary="## 用户核心需求\n- 修登录",
    )
    assert "<conversation_summary>" in prompt
    assert "以下是本对话中较早轮次的摘要，供参考：" in prompt
    assert "## 用户核心需求" in prompt
    assert "- 修登录" in prompt


def test_window_out_summary_omitted_from_system_when_empty() -> None:
    prompt = get_system_prompt_for_chat_session(agent_mode=0, window_out_summary="  ")
    assert "<conversation_summary>" not in prompt


def test_window_out_summary_not_injected_into_user_message() -> None:
    text = get_user_message_for_tool_calls("当前问题")
    assert "<conversation_summary>" not in text
    assert "<window_out_summary>" not in text
    assert "较早轮次的摘要" not in text


@patch(
    "app.services.conversation.context_summary_service.resolve_scenario",
    return_value=MagicMock(
        model_name="mock-model",
        api_key="k",
        api_base="http://localhost",
        context_limit=128000,
        temperature=0.0,
        extra_body=None,
        think_model_name=None,
        think_extra_body=None,
    ),
)
def test_format_conversation_includes_tool_calls(_mock_resolve: MagicMock) -> None:
    svc = ContextSummaryService()
    msg = ChatMessage(
        id="m1",
        conversation_id="c1",
        role="assistant",
        content_blocks=[
            TextBlock(id="t1", text="我来查一下"),
            ToolUseBlock(
                id="u1",
                tool_call_id="tc1",
                name="shell_exec",
                server_name="shell",
                mcp_tool_name="exec",
                arguments_text='{"cmd":"pytest"}',
            ),
            ToolResultBlock(
                id="r1",
                tool_call_id="tc1",
                tool_use_id="u1",
                content="3 failed, 47 passed",
            ),
        ],
    )
    text = svc.format_conversation_for_summary([msg])
    assert "[assistant]: 我来查一下" in text
    assert "[assistant tool_call]: shell_exec" in text
    assert "[tool_result]: 3 failed, 47 passed" in text

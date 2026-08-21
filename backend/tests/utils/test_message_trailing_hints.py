"""Tests for trailing hint user messages and provider projection."""

from __future__ import annotations

from app.utils.message import (
    build_trailing_hint_user_message,
    create_user_message,
    project_messages_for_provider,
)


def test_create_user_message_includes_source() -> None:
    msg = create_user_message(
        "hello",
        source={"kind": "plugin", "plugin": "iteration_hints", "form": "notice"},
    )
    assert msg["role"] == "user"
    assert msg["content"] == "hello"
    assert msg["source"]["plugin"] == "iteration_hints"


def test_project_messages_strips_source() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        create_user_message(
            "hint",
            source={"kind": "plugin", "plugin": "iteration_hints", "form": "notice"},
        ),
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "1"}],
            "reasoning_content": "r",
            "source": {"should": "drop"},
        },
    ]
    projected = project_messages_for_provider(messages)
    assert "source" not in projected[1]
    assert projected[1]["content"] == "hint"
    assert projected[2]["tool_calls"] == [{"id": "1"}]
    assert projected[2]["reasoning_content"] == "r"
    assert "source" not in projected[2]


def test_trailing_hint_iteration_only() -> None:
    msg = build_trailing_hint_user_message(iteration_hints="已搜过")
    assert msg is not None
    assert msg["source"]["plugin"] == "iteration_hints"
    assert msg["source"]["form"] == "notice"
    assert msg["content"].startswith("注意:\n")
    assert "已搜过" in msg["content"]


def test_trailing_hint_guardrail_only() -> None:
    msg = build_trailing_hint_user_message(
        guardrail_warns=["⚠️ 警告：同参失败", "⚠️ 警告：无进展"]
    )
    assert msg is not None
    assert msg["source"]["plugin"] == "tool_guardrail"
    assert "同参失败" in msg["content"]
    assert "无进展" in msg["content"]
    assert not msg["content"].startswith("注意:")


def test_trailing_hint_merged_snapshot() -> None:
    msg = build_trailing_hint_user_message(
        iteration_hints="已执行过搜索",
        guardrail_warns=["⚠️ 警告：连续失败"],
    )
    assert msg is not None
    assert msg["source"]["plugin"] == "agent_hints"
    assert msg["source"]["form"] == "snapshot"
    sections = msg["source"]["sections"]
    assert sections[0]["name"] == "iteration_hints"
    assert sections[1]["name"] == "tool_guardrail"
    # hints before warns
    assert msg["content"].index("已执行过搜索") < msg["content"].index("连续失败")


def test_trailing_hint_none_when_empty() -> None:
    assert build_trailing_hint_user_message() is None
    assert build_trailing_hint_user_message(iteration_hints="  ") is None
    assert build_trailing_hint_user_message(guardrail_warns=["", "  "]) is None

"""Tests for get_user_message_for_tool_calls datetime freezing."""

from __future__ import annotations

from datetime import datetime, timezone

from app.prompts.prompt_utils import get_user_message_for_tool_calls
from app.utils.date import get_current_datetime_str


def test_get_user_message_for_tool_calls_uses_passed_datetime() -> None:
    frozen = "2099-01-02 03:04:05"
    text = get_user_message_for_tool_calls("hi", current_datetime=frozen)
    assert frozen in text


def test_get_user_message_for_tool_calls_defaults_when_omitted() -> None:
    text = get_user_message_for_tool_calls("hi")
    # template always includes a datetime string; just ensure non-empty render
    assert "hi" in text
    assert len(text) > 10
    assert "<window_out_summary>" not in text
    assert "<conversation_summary>" not in text

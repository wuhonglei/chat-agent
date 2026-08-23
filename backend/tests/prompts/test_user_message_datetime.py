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


def test_get_current_datetime_str_formats_aware_datetime_in_local_tz() -> None:
    utc = datetime(2026, 8, 23, 5, 30, 0, tzinfo=timezone.utc)
    formatted = get_current_datetime_str(utc)
    local = utc.astimezone()
    weekdays = (
        "星期一",
        "星期二",
        "星期三",
        "星期四",
        "星期五",
        "星期六",
        "星期日",
    )
    expected = f"{local.strftime('%Y-%m-%d %H:%M:%S')} {weekdays[local.weekday()]}"
    assert formatted == expected


def test_get_current_datetime_str_keeps_naive_datetime() -> None:
    naive = datetime(2026, 8, 23, 13, 30, 0)
    assert get_current_datetime_str(naive) == "2026-08-23 13:30:00 星期日"

"""Backward-compatible re-export for tool call stream helpers."""

from app.agents.utils.tool_call_stream import (
    merge_tool_call_deltas,
    tool_call_acc_to_openai_list,
)

__all__ = ["merge_tool_call_deltas", "tool_call_acc_to_openai_list"]

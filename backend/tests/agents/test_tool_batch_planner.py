"""Tests for path-aware tool batch planning."""

from __future__ import annotations

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.agents.tool_batch_planner import (
    paths_overlap,
    plan_tool_batch_segments,
)


def _tc(name: str, arguments: str, call_id: str) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id=call_id,
        type="function",
        function=Function(name=name, arguments=arguments),
    )


def test_paths_overlap_prefix() -> None:
    assert paths_overlap("/a/b", "/a/b/c")
    assert paths_overlap("/a/b/c", "/a/b")
    assert paths_overlap("/a/b/c", "/a/b/c")
    # Siblings share a parent but neither is a prefix of the other.
    assert not paths_overlap("/a/b/c", "/a/b/d")
    assert not paths_overlap("/a/b", "/x/y")


def test_same_file_writes_split_into_two_segments() -> None:
    calls = [
        _tc(
            "file_write_file",
            '{"file_path":"/mnt/user-data/workspace/a.txt","content":"1"}',
            "c1",
        ),
        _tc(
            "file_write_file",
            '{"file_path":"/mnt/user-data/workspace/a.txt","content":"2"}',
            "c2",
        ),
        _tc(
            "file_read_file",
            '{"file_path":"/mnt/user-data/workspace/b.txt"}',
            "c3",
        ),
    ]
    segments = plan_tool_batch_segments(calls)
    assert len(segments) == 2
    assert [tc.id for tc in segments[0]] == ["c1"]
    assert [tc.id for tc in segments[1]] == ["c2", "c3"]


def test_different_files_stay_in_one_segment() -> None:
    calls = [
        _tc(
            "file_write_file",
            '{"file_path":"/mnt/user-data/workspace/a.txt","content":"1"}',
            "c1",
        ),
        _tc(
            "file_read_file",
            '{"file_path":"/mnt/user-data/workspace/b.txt"}',
            "c2",
        ),
    ]
    segments = plan_tool_batch_segments(calls)
    assert len(segments) == 1
    assert [tc.id for tc in segments[0]] == ["c1", "c2"]


def test_shell_joins_current_group_without_breaking() -> None:
    calls = [
        _tc(
            "file_write_file",
            '{"file_path":"/mnt/user-data/workspace/a.txt","content":"1"}',
            "c1",
        ),
        _tc("shell_exec", '{"command":"ls","description":"list files"}', "c2"),
        _tc(
            "file_read_file",
            '{"file_path":"/mnt/user-data/workspace/b.txt"}',
            "c3",
        ),
    ]
    segments = plan_tool_batch_segments(calls)
    assert len(segments) == 1
    assert [tc.id for tc in segments[0]] == ["c1", "c2", "c3"]

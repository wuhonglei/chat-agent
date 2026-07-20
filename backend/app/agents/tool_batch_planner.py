"""Plan parallel segments for tool-call batches (path-conflict aware)."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.mcp.constants import (
    FILE_SERVER,
    PATH_SCOPED_FILE_BARE_TOOLS,
    PRESENT_FILES_BARE,
)
from app.mcp.tool_naming import is_llm_tool


def paths_overlap(left: str, right: str) -> bool:
    """Return True when either path is a prefix of the other (hermes-style)."""
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    if not left_parts or not right_parts:
        return left == right
    common_len = min(len(left_parts), len(right_parts))
    return left_parts[:common_len] == right_parts[:common_len]


def _parse_arguments(tool_call: ChatCompletionMessageFunctionToolCall) -> dict[str, Any]:
    raw = tool_call.function.arguments or "{}"
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_tool_paths(
    tool_name: str, arguments: dict[str, Any]
) -> list[str]:
    """Extract normalized virtual paths for path-scoped file tools."""
    for bare in PATH_SCOPED_FILE_BARE_TOOLS:
        if not is_llm_tool(tool_name, FILE_SERVER, bare):
            continue
        if bare == PRESENT_FILES_BARE:
            filepaths = arguments.get("filepaths")
            if not isinstance(filepaths, list):
                return []
            return [str(p) for p in filepaths if isinstance(p, str) and p]
        file_path = arguments.get("file_path")
        if isinstance(file_path, str) and file_path:
            return [file_path]
        return []
    return []


def _paths_conflict_with_reserved(
    candidate_paths: list[str], reserved_paths: list[str]
) -> bool:
    for candidate in candidate_paths:
        for reserved in reserved_paths:
            if paths_overlap(candidate, reserved):
                return True
    return False


def plan_tool_batch_segments(
    tool_calls: list[ChatCompletionMessageFunctionToolCall],
) -> list[list[ChatCompletionMessageFunctionToolCall]]:
    """Split tool calls into sequential parallel groups by path overlap.

    Non-path-scoped tools join the current group without reserving paths.
    """
    if not tool_calls:
        return []

    segments: list[list[ChatCompletionMessageFunctionToolCall]] = []
    current: list[ChatCompletionMessageFunctionToolCall] = []
    reserved_paths: list[str] = []

    for tool_call in tool_calls:
        arguments = _parse_arguments(tool_call)
        paths = extract_tool_paths(tool_call.function.name, arguments)

        if paths and _paths_conflict_with_reserved(paths, reserved_paths):
            if current:
                segments.append(current)
            current = [tool_call]
            reserved_paths = list(paths)
            continue

        current.append(tool_call)
        reserved_paths.extend(paths)

    if current:
        segments.append(current)
    return segments

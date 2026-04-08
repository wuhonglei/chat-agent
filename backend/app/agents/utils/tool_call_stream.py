"""流式 ChatCompletionChunk 中 tool_calls 的 index 聚合。"""

from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function


def merge_tool_call_deltas(
    acc: dict[int, dict[str, Any]],
    delta_tool_calls: list[Any] | None,
) -> None:
    """将 chunk.delta.tool_calls 合并到 acc（按 index）。"""
    if not delta_tool_calls:
        return
    for tc in delta_tool_calls:
        idx = getattr(tc, "index", None)
        if idx is None:
            continue
        if idx not in acc:
            acc[idx] = {"id": None, "name": None, "arguments": ""}
        if getattr(tc, "id", None):
            acc[idx]["id"] = tc.id
        fn = getattr(tc, "function", None)
        if fn is not None:
            name = getattr(fn, "name", None)
            if name:
                acc[idx]["name"] = name
            args = getattr(fn, "arguments", None)
            if args:
                acc[idx]["arguments"] = acc[idx]["arguments"] + args


def tool_call_acc_to_openai_list(
    acc: dict[int, dict[str, Any]],
) -> list[ChatCompletionMessageFunctionToolCall]:
    out: list[ChatCompletionMessageFunctionToolCall] = []
    for idx in sorted(acc.keys()):
        row = acc[idx]
        out.append(
            ChatCompletionMessageFunctionToolCall(
                id=row.get("id") or "",
                type="function",
                function=Function(
                    name=row.get("name") or "",
                    arguments=row.get("arguments") or "",
                ),
            )
        )
    return out

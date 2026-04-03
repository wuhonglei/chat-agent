from __future__ import annotations

import json
from typing import Any

from app.schemas.chat import (
    ContentBlock,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    collect_content_from_blocks,
    collect_reasoning_from_blocks,
)
from app.schemas.llm import ToolResultMessage


class ContentBlocksAggregator:
    def __init__(self) -> None:
        self.blocks: list[ContentBlock] = []
        self._seq = 0
        self._current_text_block_id: str | None = None
        self._current_thinking_block_id: str | None = None
        self._tool_index_to_use_block_id: dict[int, str] = {}
        self._tool_call_to_use_block_id: dict[str, str] = {}

    def _next_id(self) -> str:
        self._seq += 1
        return f"cb_{self._seq:06d}"

    def _find_block(self, block_id: str) -> ContentBlock | None:
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None

    def append_thinking_delta(self, delta: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not delta:
            return events
        if not self._current_thinking_block_id:
            new_block = ThinkingBlock(id=self._next_id(), text=delta)
            self.blocks.append(new_block)
            self._current_thinking_block_id = new_block.id
            self._current_text_block_id = None
            events.append({"op": "append", "block": new_block.model_dump(mode="json")})
            return events
        existing_block = self._find_block(self._current_thinking_block_id)
        if isinstance(existing_block, ThinkingBlock):
            existing_block.text += delta
            events.append(
                {"op": "delta", "block_id": existing_block.id, "delta": delta}
            )
        return events

    def append_text_delta(self, delta: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not delta:
            return events
        if not self._current_text_block_id:
            new_block = TextBlock(id=self._next_id(), text=delta)
            self.blocks.append(new_block)
            self._current_text_block_id = new_block.id
            self._current_thinking_block_id = None
            events.append({"op": "append", "block": new_block.model_dump(mode="json")})
            return events
        existing_block = self._find_block(self._current_text_block_id)
        if isinstance(existing_block, TextBlock):
            existing_block.text += delta
            events.append(
                {"op": "delta", "block_id": existing_block.id, "delta": delta}
            )
        return events

    def process_tool_call_deltas(
        self, delta_tool_calls: list[Any] | None
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not delta_tool_calls:
            return events
        self._current_text_block_id = None
        self._current_thinking_block_id = None
        for tc in delta_tool_calls:
            idx = getattr(tc, "index", None)
            if idx is None:
                continue
            use_block_id = self._tool_index_to_use_block_id.get(idx)
            if use_block_id is None:
                new_block = ToolUseBlock(id=self._next_id())
                self.blocks.append(new_block)
                self._tool_index_to_use_block_id[idx] = new_block.id
                use_block_id = new_block.id
                events.append(
                    {"op": "append", "block": new_block.model_dump(mode="json")}
                )
            existing_block = self._find_block(use_block_id)
            if not isinstance(existing_block, ToolUseBlock):
                continue
            updates: dict[str, Any] = {}
            if getattr(tc, "id", None):
                existing_block.tool_call_id = tc.id
                self._tool_call_to_use_block_id[tc.id] = existing_block.id
                updates["tool_call_id"] = tc.id
            fn = getattr(tc, "function", None)
            arguments_delta = ""
            if fn is not None:
                if getattr(fn, "name", None):
                    existing_block.name = fn.name
                    updates["name"] = fn.name
                if getattr(fn, "arguments", None):
                    arguments_delta = fn.arguments
                    existing_block.arguments_text += arguments_delta
            if arguments_delta or updates:
                events.append(
                    {
                        "op": "tool_delta",
                        "block_id": existing_block.id,
                        "arguments_delta": arguments_delta,
                        **updates,
                    }
                )
        return events

    def finalize_round(self) -> dict[str, Any]:
        for block in self.blocks:
            if not isinstance(block, ToolUseBlock):
                continue
            if not block.arguments_text:
                block.arguments_json = {}
                continue
            try:
                block.arguments_json = json.loads(block.arguments_text)
            except Exception:
                block.arguments_json = None
        return {"op": "finalize_round"}

    def append_tool_result(self, tool_result: ToolResultMessage) -> dict[str, Any]:
        tool_use_id = self._tool_call_to_use_block_id.get(tool_result.tool_call_id)
        if not tool_use_id:
            orphan_block = ToolUseBlock(
                id=self._next_id(),
                tool_call_id=tool_result.tool_call_id,
            )
            self.blocks.append(orphan_block)
            tool_use_id = orphan_block.id
        block = ToolResultBlock(
            id=self._next_id(),
            tool_call_id=tool_result.tool_call_id,
            tool_use_id=tool_use_id,
            is_error=tool_result.is_error,
            content=tool_result.content or "",
            summary=tool_result.summary,
        )
        self.blocks.append(block)
        return {"op": "append", "block": block.model_dump(mode="json")}

    def get_content(self) -> str:
        return collect_content_from_blocks(self.blocks)

    def get_reasoning(self) -> str:
        return collect_reasoning_from_blocks(self.blocks)

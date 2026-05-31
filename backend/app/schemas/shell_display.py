"""Structured shell execution payloads for MCP and frontend display."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ShellExecStructuredContent(BaseModel):
    """MCP ToolResult.structured_content for shell execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    output_truncated: bool = False
    blocked: bool = False
    block_reason: str | None = None
    duration_ms: int = 0


class ShellExecDisplayItem(BaseModel):
    """Single entry in ToolResultBlock.structured_content_for_display."""

    type: Literal["shell_exec"] = "shell_exec"
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    output_truncated: bool = False
    blocked: bool = False
    block_reason: str | None = None
    duration_ms: int = 0

    @classmethod
    def from_structured_content(
        cls, structured_content: dict[str, Any] | ShellExecStructuredContent
    ) -> ShellExecDisplayItem:
        if isinstance(structured_content, ShellExecStructuredContent):
            payload = structured_content.model_dump(mode="json")
        else:
            payload = dict(structured_content)
        return cls.model_validate(payload)

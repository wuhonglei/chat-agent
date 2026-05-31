"""Shell tool execution result container."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.shell_display import ShellExecStructuredContent


@dataclass(frozen=True)
class ShellToolExecuteResult:
    content: str
    structured_content: ShellExecStructuredContent | None = None

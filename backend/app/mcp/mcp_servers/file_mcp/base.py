"""Base class for file MCP tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.utils.logger import conversation_id_var, user_id_var


@dataclass
class ToolContext:
    """Context passed to tool execution.

    Reads user_id and workspace_id from contextvars set by tool_executor.
    """

    @property
    def user_id(self) -> str:
        return user_id_var.get() or ""

    @property
    def workspace_id(self) -> str:
        return conversation_id_var.get() or ""


@dataclass
class ToolResult:
    """Result from tool execution."""

    content: str
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


class ToolBase(ABC):
    """Abstract base class for MCP tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute the tool with given arguments and context."""

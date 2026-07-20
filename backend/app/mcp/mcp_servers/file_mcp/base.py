"""Base class for file MCP tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from fastmcp.tools.tool import ToolResult as FastMCPToolResult
from mcp.types import CallToolResult

from app.utils.context import get_request_context


@dataclass
class ToolContext:
    """Context passed to tool execution.

    Reads user_id and conversation_id from RequestContext set by tool_executor.
    """

    @property
    def user_id(self) -> str:
        return get_request_context().user_id or ""

    @property
    def conversation_id(self) -> str:
        return get_request_context().conversation_id or ""


@dataclass
class ToolResult:
    """Result from tool execution."""

    content: str
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


class _ErrorAwareFastMCPToolResult(FastMCPToolResult):
    """FastMCP ToolResult that can emit MCP ``isError`` via ``to_mcp_result``."""

    def __init__(
        self,
        content: Any = None,
        structured_content: dict[str, Any] | Any | None = None,
        meta: dict[str, Any] | None = None,
        *,
        is_error: bool = False,
    ) -> None:
        super().__init__(
            content=content,
            structured_content=structured_content,
            meta=meta,
        )
        object.__setattr__(self, "_mcp_is_error", is_error)

    def to_mcp_result(
        self,
    ) -> list[Any] | tuple[list[Any], dict[str, Any]] | CallToolResult:
        if getattr(self, "_mcp_is_error", False):
            kwargs: dict[str, Any] = {
                "content": self.content,
                "structuredContent": self.structured_content,
                "isError": True,
            }
            if self.meta is not None:
                kwargs["_meta"] = self.meta
            return CallToolResult(**kwargs)
        return super().to_mcp_result()


def to_fastmcp_tool_result(result: ToolResult) -> FastMCPToolResult:
    """Wrap internal ToolResult for FastMCP, preserving ``is_error`` as MCP isError."""
    return _ErrorAwareFastMCPToolResult(
        content=result.content,
        structured_content=result.structured_content,
        is_error=result.is_error,
    )


class ToolBase(ABC):
    """Abstract base class for MCP tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute the tool with given arguments and context."""

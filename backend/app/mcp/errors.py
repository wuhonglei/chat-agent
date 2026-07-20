"""MCP tool call errors."""

from __future__ import annotations


class ToolArgumentValidationError(ValueError):
    """Raised when tool arguments fail JSON Schema validation."""

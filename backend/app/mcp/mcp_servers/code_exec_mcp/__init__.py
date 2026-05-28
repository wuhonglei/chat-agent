"""Code Exec MCP package. Import ``server`` module directly for the FastMCP instance."""

from __future__ import annotations

from typing import Any

__all__ = ["mcp"]


def __getattr__(name: str) -> Any:
    if name == "mcp":
        from .server import mcp

        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

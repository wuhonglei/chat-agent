"""Transport utility helpers."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP


def is_local_fastmcp(server_instance: Any) -> bool:
    return isinstance(server_instance, FastMCP)

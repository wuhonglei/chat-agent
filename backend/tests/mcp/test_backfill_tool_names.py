"""Unit tests for backfill bare-name resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backfill_tool_use_block_names.py"
_spec = importlib.util.spec_from_file_location("backfill_tool_use_block_names", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_resolve_bare_web_search() -> None:
    server, llm, fallback = _mod._resolve_bare_name("web_search", agent_mode=False)
    assert server == "tavily"
    assert llm == "tavily_web_search"
    assert fallback is False


def test_resolve_prefixed_name() -> None:
    llm, server, mcp = _mod._resolve_prefixed_name("file_read_file")
    assert server == "file"
    assert mcp == "read_file"
    assert llm == "file_read_file"

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


def test_process_block_legacy_llm_name_remap_even_when_old_fields_valid() -> None:
    block = {
        "type": "tool_use",
        "id": "tu_0",
        "name": "file_load_skill",
        "server_name": "file",
        "mcp_tool_name": "load_skill",
    }
    updated, changed, _fallback = _mod._process_block(block, agent_mode=True)
    assert changed is True
    assert updated["name"] == "skill_manager_load_skill"
    assert updated["server_name"] == "skill_manager"
    assert updated["mcp_tool_name"] == "load_skill"


@pytest.mark.parametrize(
    ("legacy_name", "llm_name", "server", "mcp"),
    [
        (
            "file_load_skill",
            "skill_manager_load_skill",
            "skill_manager",
            "load_skill",
        ),
        (
            "code-exec_execute_code",
            "code_execute_code",
            "code",
            "execute_code",
        ),
        (
            "code-exec_list_runtimes",
            "code_list_runtimes",
            "code",
            "list_runtimes",
        ),
    ],
)
def test_process_block_legacy_llm_name_remap(
    legacy_name: str,
    llm_name: str,
    server: str,
    mcp: str,
) -> None:
    block = {
        "type": "tool_use",
        "id": "tu_1",
        "name": legacy_name,
    }
    updated, changed, fallback = _mod._process_block(block, agent_mode=True)
    assert changed is True
    assert fallback is False
    assert updated["name"] == llm_name
    assert updated["server_name"] == server
    assert updated["mcp_tool_name"] == mcp


def test_process_block_skips_already_remapped_legacy_name() -> None:
    block = {
        "type": "tool_use",
        "id": "tu_2",
        "name": "skill_manager_load_skill",
        "server_name": "skill_manager",
        "mcp_tool_name": "load_skill",
    }
    updated, changed, fallback = _mod._process_block(block, agent_mode=True)
    assert changed is False
    assert fallback is False
    assert updated == block

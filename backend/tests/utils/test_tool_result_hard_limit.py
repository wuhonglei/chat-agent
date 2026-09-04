from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.config import ToolResultHardLimitConfig
from app.schemas.llm import ToolResultMessage
from app.utils.tool_result_hard_limit import (
    _allocate_head_tail,
    apply_hard_limit,
    enforce_turn_budget,
    extract_bare_tool_name,
    is_hard_limited,
    resolve_max_chars,
)
from app.vfs.paths import get_paths


def _msg(content: str, tool_call_id: str = "call_1") -> ToolResultMessage:
    return ToolResultMessage(
        role="tool",
        tool_call_id=tool_call_id,
        is_error=False,
        content=content,
    )


def _config(**overrides: object) -> ToolResultHardLimitConfig:
    base = ToolResultHardLimitConfig(
        enabled=True,
        max_chars=100,
        preview_head_chars=10,
        preview_tail_chars=5,
        turn_budget_chars=150,
        tool_overrides={"exec": 50, "web_pages_extract": 80},
        exempt_bare_names=["read_file"],
    )
    return base.model_copy(update=overrides)


def test_extract_bare_tool_name() -> None:
    assert extract_bare_tool_name("shell_exec") == "exec"
    assert extract_bare_tool_name("file_read_file") == "read_file"
    assert extract_bare_tool_name("tavily_web_search") == "web_search"


def test_resolve_max_chars_llm_and_bare_keys() -> None:
    cfg = _config(tool_overrides={"exec": 50, "shell_exec": 40})
    assert resolve_max_chars("shell_exec", cfg) == 40
    cfg2 = _config(tool_overrides={"exec": 50})
    assert resolve_max_chars("shell_exec", cfg2) == 50
    assert resolve_max_chars("tavily_web_search", cfg2) == 100


def test_resolve_max_chars_zero_disables_layer2() -> None:
    cfg = _config(tool_overrides={"exec": 0})
    assert resolve_max_chars("shell_exec", cfg) is None


def test_allocate_head_tail_uses_preview_ratio() -> None:
    assert _allocate_head_tail(30_000, head_ratio_chars=2_000, tail_ratio_chars=1_000) == (
        20_000,
        10_000,
    )
    assert _allocate_head_tail(0, head_ratio_chars=2_000, tail_ratio_chars=1_000) == (0, 0)
    assert _allocate_head_tail(9, head_ratio_chars=0, tail_ratio_chars=0) == (6, 3)


def test_agent_mode_0_passthrough_defers_to_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    content = "H" * 40 + "M" * 40 + "T" * 40
    result = apply_hard_limit(
        _msg(content),
        tool_name="tavily_web_search",
        agent_mode=0,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=50),
    )
    assert result.content == content
    assert not is_hard_limited(result.content)
    persist_dir = tmp_path / "u1" / "conversations" / "c1" / "workspace" / "tool-results"
    assert not persist_dir.exists()


def test_agent_mode_1_persists_to_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    content = "HEAD_START_" + ("x" * 80) + "_TAIL_END"
    result = apply_hard_limit(
        _msg(content, tool_call_id="tc_shell"),
        tool_name="shell_exec",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=50, preview_head_chars=10, preview_tail_chars=9),
    )
    assert "full output persisted" in result.content
    assert f"{len(content)} chars total, 1 lines" in result.content
    assert "/mnt/user-data/workspace/tool-results/shell_exec-1.txt" in result.content
    assert "read_file" in result.content
    physical = (
        tmp_path
        / "u1"
        / "conversations"
        / "c1"
        / "workspace"
        / "tool-results"
        / "shell_exec-1.txt"
    )
    assert physical.is_file()
    assert physical.read_text(encoding="utf-8") == content


def test_persist_filename_increments_per_full_tool_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    cfg = _config(max_chars=10, tool_overrides={})
    content = "x" * 40
    first = apply_hard_limit(
        _msg(content, tool_call_id="c1"),
        tool_name="tavily_web_search",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=cfg,
    )
    second = apply_hard_limit(
        _msg(content, tool_call_id="c2"),
        tool_name="tavily_web_search",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=cfg,
    )
    other = apply_hard_limit(
        _msg(content, tool_call_id="c3"),
        tool_name="tavily_web_pages_extract",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=cfg,
    )
    assert "/mnt/user-data/workspace/tool-results/tavily_web_search-1.txt" in first.content
    assert "/mnt/user-data/workspace/tool-results/tavily_web_search-2.txt" in second.content
    assert (
        "/mnt/user-data/workspace/tool-results/tavily_web_pages_extract-1.txt"
        in other.content
    )
    persist_dir = tmp_path / "u1" / "conversations" / "c1" / "workspace" / "tool-results"
    assert (persist_dir / "tavily_web_search-1.txt").is_file()
    assert (persist_dir / "tavily_web_search-2.txt").is_file()
    assert (persist_dir / "tavily_web_pages_extract-1.txt").is_file()


def test_sanitize_persist_stem_strips_unsafe_chars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    result = apply_hard_limit(
        _msg("x" * 40, tool_call_id="c1"),
        tool_name="Weird/Tool Name!",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=10, tool_overrides={}),
    )
    assert "/mnt/user-data/workspace/tool-results/weird_tool_name-1.txt" in result.content
    physical = (
        tmp_path
        / "u1"
        / "conversations"
        / "c1"
        / "workspace"
        / "tool-results"
        / "weird_tool_name-1.txt"
    )
    assert physical.is_file()


def test_persist_skips_occupied_seq_on_excl_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    persist_dir = tmp_path / "u1" / "conversations" / "c1" / "workspace" / "tool-results"
    persist_dir.mkdir(parents=True)
    (persist_dir / "shell_exec-1.txt").write_text("occupied", encoding="utf-8")

    result = apply_hard_limit(
        _msg("x" * 40, tool_call_id="c1"),
        tool_name="shell_exec",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=10, tool_overrides={}),
    )
    assert "/mnt/user-data/workspace/tool-results/shell_exec-2.txt" in result.content
    assert (persist_dir / "shell_exec-2.txt").read_text(encoding="utf-8") == "x" * 40
    assert (persist_dir / "shell_exec-1.txt").read_text(encoding="utf-8") == "occupied"


def test_tool_overrides_trigger_earlier_for_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    cfg = _config(max_chars=200, tool_overrides={"exec": 30})
    content = "a" * 50
    # Non-agent always passthrough regardless of overrides.
    untouched = apply_hard_limit(
        _msg(content),
        tool_name="shell_exec",
        agent_mode=0,
        user_id=None,
        conversation_id=None,
        config=cfg,
    )
    assert untouched.content == content

    persisted = apply_hard_limit(
        _msg(content, tool_call_id="tc_exec"),
        tool_name="shell_exec",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=cfg,
    )
    assert is_hard_limited(persisted.content)
    assert "full output persisted" in persisted.content


def test_override_zero_skips_layer2_unless_force() -> None:
    cfg = _config(max_chars=10, tool_overrides={"exec": 0})
    content = "b" * 50
    skipped = apply_hard_limit(
        _msg(content),
        tool_name="shell_exec",
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=cfg,
    )
    assert skipped.content == content

    forced = apply_hard_limit(
        _msg(content),
        tool_name="shell_exec",
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=cfg,
        force=True,
    )
    assert is_hard_limited(forced.content)


def test_read_file_fully_exempt_passthrough(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: type(get_paths())(base_dir=tmp_path),
    )
    content = "R" * 200
    result = apply_hard_limit(
        _msg(content, tool_call_id="tc_read"),
        tool_name="file_read_file",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=50),
    )
    assert result.content == content
    assert not is_hard_limited(result.content)
    persist_dir = tmp_path / "u1" / "conversations" / "c1" / "workspace" / "tool-results"
    assert not persist_dir.exists()


def test_read_file_exempt_ignores_force() -> None:
    content = "R" * 200
    result = apply_hard_limit(
        _msg(content),
        tool_name="file_read_file",
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=_config(max_chars=50),
        force=True,
    )
    assert result.content == content
    assert not is_hard_limited(result.content)


def test_turn_budget_noop_in_non_agent() -> None:
    cfg = _config(
        max_chars=10_000,
        tool_overrides={},
        turn_budget_chars=80,
        preview_head_chars=8,
        preview_tail_chars=4,
    )
    messages = [
        _msg("a" * 50, tool_call_id="c1"),
        _msg("b" * 60, tool_call_id="c2"),
    ]
    out = enforce_turn_budget(
        messages,
        tool_name_by_call_id={"c1": "tavily_web_search", "c2": "shell_exec"},
        agent_mode=0,
        user_id=None,
        conversation_id=None,
        config=cfg,
    )
    assert out[0].content == messages[0].content
    assert out[1].content == messages[1].content


def test_turn_budget_skips_exempt_read_file() -> None:
    cfg = _config(
        max_chars=10_000,
        tool_overrides={},
        turn_budget_chars=80,
        preview_head_chars=8,
        preview_tail_chars=4,
        exempt_bare_names=["read_file"],
    )
    read_content = "R" * 100
    other_content = "b" * 60
    messages = [
        _msg(read_content, tool_call_id="c_read"),
        _msg(other_content, tool_call_id="c_shell"),
    ]
    out = enforce_turn_budget(
        messages,
        tool_name_by_call_id={
            "c_read": "file_read_file",
            "c_shell": "shell_exec",
        },
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=cfg,
    )
    assert out[0].content == read_content
    assert not is_hard_limited(out[0].content)
    assert is_hard_limited(out[1].content)


def test_persist_failure_falls_back_to_truncate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenPaths:
        def ensure_sandbox_work_dir(self, user_id: str, conversation_id: str) -> Path:
            raise OSError("disk full")

    monkeypatch.setattr(
        "app.utils.tool_result_hard_limit.get_paths",
        lambda: _BrokenPaths(),
    )
    content = "Z" * 200
    result = apply_hard_limit(
        _msg(content),
        tool_name="shell_exec",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=50, preview_head_chars=10, preview_tail_chars=5),
    )
    assert is_hard_limited(result.content)
    assert "full output persisted" not in result.content
    assert "无法回读完整原文" in result.content
    assert result.content.startswith("Z" * 33)
    assert result.content.count("Z") >= 50


def test_force_truncate_still_uses_preview_sizes() -> None:
    content = "b" * 200
    result = apply_hard_limit(
        _msg(content),
        tool_name="shell_exec",
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=_config(max_chars=10_000, preview_head_chars=8, preview_tail_chars=4),
        force=True,
    )
    assert is_hard_limited(result.content)
    assert result.content.startswith("b" * 8)
    assert "bbbb" in result.content  # tail
    assert len(result.content) < 200


def test_turn_budget_forces_largest() -> None:
    cfg = _config(
        max_chars=10_000,
        tool_overrides={},
        turn_budget_chars=80,
        preview_head_chars=8,
        preview_tail_chars=4,
    )
    messages = [
        _msg("a" * 50, tool_call_id="c1"),
        _msg("b" * 60, tool_call_id="c2"),
    ]
    out = enforce_turn_budget(
        messages,
        tool_name_by_call_id={"c1": "tavily_web_search", "c2": "shell_exec"},
        agent_mode=1,
        user_id=None,
        conversation_id=None,
        config=cfg,
    )
    assert is_hard_limited(out[1].content)
    assert sum(len(m.content) for m in out) <= cfg.turn_budget_chars or is_hard_limited(
        out[0].content
    )


def test_under_threshold_unchanged() -> None:
    result = apply_hard_limit(
        _msg("short"),
        tool_name="shell_exec",
        agent_mode=1,
        user_id="u1",
        conversation_id="c1",
        config=_config(max_chars=100),
    )
    assert result.content == "short"

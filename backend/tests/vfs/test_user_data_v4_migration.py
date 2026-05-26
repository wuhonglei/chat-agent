"""Disk layout migration smoke tests (v3 → v4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b4c5d6e7f8a9_user_data_v4_migration.py"
)
_spec = importlib.util.spec_from_file_location(
    "user_data_v4_migration", _MIGRATION_PATH
)
assert _spec and _spec.loader
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)


@pytest.fixture
def user_dir(tmp_path: Path) -> Path:
    uid = "user-1"
    conv = "conv-1"
    ws_legacy = tmp_path / uid / "workspaces" / conv
    up_legacy = tmp_path / uid / "uploads" / conv
    ws_legacy.mkdir(parents=True)
    up_legacy.mkdir(parents=True)
    (ws_legacy / "hello.txt").write_text("workspace", encoding="utf-8")
    (up_legacy / "doc.pdf").write_bytes(b"%PDF-1.4")
    return tmp_path / uid


def test_migrate_user_disk_moves_workspace_and_uploads(user_dir: Path) -> None:
    _migration._migrate_user_disk(user_dir)
    conv_root = user_dir / "conversations" / "conv-1"
    assert (conv_root / "workspace" / "hello.txt").read_text(
        encoding="utf-8"
    ) == "workspace"
    assert (conv_root / "uploads" / "doc.pdf").is_file()
    assert (conv_root / "outputs").is_dir()


def test_rewrite_virtual_path_string() -> None:
    assert (
        _migration._rewrite_virtual_path_string("/workspace/a.txt")
        == "/mnt/user-data/workspace/a.txt"
    )
    assert (
        _migration._rewrite_virtual_path_string("/uploads/x.pdf")
        == "/mnt/user-data/uploads/x.pdf"
    )
    assert (
        _migration._rewrite_virtual_path_string("/mnt/user-data/workspace/x")
        == "/mnt/user-data/workspace/x"
    )

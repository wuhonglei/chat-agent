"""Tests for centralized user_data path layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.vfs.config import vfs_config
from app.vfs.paths import VIRTUAL_PATH_PREFIX, Paths


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    return Paths(base_dir=tmp_path)


def test_ensure_conversation_dirs_creates_layout(paths: Paths) -> None:
    paths.ensure_conversation_dirs("user-1", "conv-1")
    conv = paths.conversation_dir("user-1", "conv-1")
    assert (conv / "workspace").is_dir()
    assert (conv / "uploads").is_dir()
    assert (conv / "outputs").is_dir()


def test_resolve_user_data_virtual_path_workspace(paths: Paths) -> None:
    paths.ensure_conversation_dirs("user-1", "conv-1")
    physical, kind = paths.resolve_user_data_virtual_path(
        f"{vfs_config.workspace_prefix}notes.txt",
        "user-1",
        "conv-1",
    )
    assert kind == "workspace"
    assert physical == paths.sandbox_work_dir("user-1", "conv-1") / "notes.txt"


def test_resolve_user_data_virtual_path_rejects_traversal(paths: Paths) -> None:
    paths.ensure_conversation_dirs("user-1", "conv-1")
    with pytest.raises(ValueError, match="path traversal"):
        paths.resolve_user_data_virtual_path(
            f"{vfs_config.workspace_prefix}../secret.txt",
            "user-1",
            "conv-1",
        )


def test_validate_conversation_id_rejects_unsafe(paths: Paths) -> None:
    with pytest.raises(ValueError, match="invalid conversation_id"):
        paths.validate_conversation_id("../bad")


def test_virtual_path_prefix_constant() -> None:
    assert VIRTUAL_PATH_PREFIX == "/mnt/user-data"

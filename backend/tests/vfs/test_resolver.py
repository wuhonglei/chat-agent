"""Tests for shared relative path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.vfs.resolver import resolve_relative_under_root


def test_resolve_relative_under_root_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError, match="forbidden path"):
        resolve_relative_under_root(root, "../outside.txt")

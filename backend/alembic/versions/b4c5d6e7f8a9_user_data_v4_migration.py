"""user_data v4：conversations 目录布局 + 虚拟路径 /mnt/user-data/*

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-25

"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_ROOT = _BACKEND_ROOT / "data" / "user_data"
STORAGE_VERSION_V3 = 3
STORAGE_VERSION_V4 = 4

_LEGACY_UPLOAD_TOP = frozenset({"raw", "derived"})
_VIRTUAL_REWRITES = (
    ("/workspace/", "/mnt/user-data/workspace/"),
    ("/uploads/", "/mnt/user-data/uploads/"),
)


def _copy_file_if_needed(src: Path, dest: Path) -> None:
    if dest.is_file():
        if src.is_file() and dest.stat().st_size == src.stat().st_size:
            return
        return
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _merge_tree_into(src: Path, dest: Path) -> None:
    if not src.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dest / child.name
        if child.is_dir():
            if target.exists() and target.is_dir():
                _merge_tree_into(child, target)
            elif not target.exists():
                shutil.move(str(child), str(target))
            else:
                _copy_file_if_needed(child, target)
        else:
            _copy_file_if_needed(child, target)


def _migrate_conversation_workspace(user_dir: Path, conversation_id: str) -> None:
    legacy = user_dir / "workspaces" / conversation_id
    if not legacy.is_dir():
        return
    dest = user_dir / "conversations" / conversation_id / "workspace"
    _merge_tree_into(legacy, dest)


def _migrate_conversation_uploads(user_dir: Path, conversation_id: str) -> None:
    legacy = user_dir / "uploads" / conversation_id
    if not legacy.is_dir():
        return
    dest = user_dir / "conversations" / conversation_id / "uploads"
    _merge_tree_into(legacy, dest)


def _ensure_outputs_dir(user_dir: Path, conversation_id: str) -> None:
    outputs = user_dir / "conversations" / conversation_id / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)


def _migrate_user_disk(user_dir: Path) -> None:
    workspaces_root = user_dir / "workspaces"
    if workspaces_root.is_dir():
        for conv_dir in workspaces_root.iterdir():
            if conv_dir.is_dir():
                _migrate_conversation_workspace(user_dir, conv_dir.name)
                _ensure_outputs_dir(user_dir, conv_dir.name)

    uploads_root = user_dir / "uploads"
    if uploads_root.is_dir():
        for child in uploads_root.iterdir():
            if not child.is_dir() or child.name in _LEGACY_UPLOAD_TOP:
                continue
            _migrate_conversation_uploads(user_dir, child.name)
            _ensure_outputs_dir(user_dir, child.name)

    conversations_root = user_dir / "conversations"
    if conversations_root.is_dir():
        for conv_dir in conversations_root.iterdir():
            if conv_dir.is_dir():
                _ensure_outputs_dir(user_dir, conv_dir.name)


def _migrate_all_user_data() -> None:
    if not USER_DATA_ROOT.is_dir():
        return
    for user_dir in USER_DATA_ROOT.iterdir():
        if user_dir.is_dir():
            _migrate_user_disk(user_dir)


def _rewrite_virtual_path_string(value: str) -> str:
    if value.startswith("/mnt/user-data/"):
        return value
    updated = value
    for old_prefix, new_prefix in _VIRTUAL_REWRITES:
        if updated == old_prefix.rstrip("/"):
            return new_prefix.rstrip("/")
        if updated.startswith(old_prefix):
            updated = new_prefix + updated[len(old_prefix) :]
    return updated


def _rewrite_virtual_paths_deep(value: Any) -> Any:
    if isinstance(value, str):
        return _rewrite_virtual_path_string(value)
    if isinstance(value, dict):
        return {key: _rewrite_virtual_paths_deep(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_virtual_paths_deep(item) for item in value]
    return value


def _bump_storage_version(block: dict[str, Any]) -> dict[str, Any]:
    updated = dict(block)
    if updated.get("storage_version") == STORAGE_VERSION_V3:
        updated["storage_version"] = STORAGE_VERSION_V4
    markdown = updated.get("markdown")
    if isinstance(markdown, dict):
        md = dict(markdown)
        if md.get("storage_version") == STORAGE_VERSION_V3:
            md["storage_version"] = STORAGE_VERSION_V4
        updated["markdown"] = md
    return updated


def _migrate_message_content_blocks() -> None:
    bind = op.get_bind()
    messages = sa.table(
        "messages",
        sa.column("id", sa.String()),
        sa.column("content_blocks", sa.JSON()),
    )

    rows = bind.execute(
        sa.select(messages.c.id, messages.c.content_blocks).where(
            messages.c.content_blocks.is_not(None)
        )
    ).mappings()

    for row in rows:
        content_blocks = row["content_blocks"]
        if not isinstance(content_blocks, list):
            continue

        updated_blocks: list[Any] = []
        changed = False
        for block in content_blocks:
            if not isinstance(block, dict):
                rewritten = _rewrite_virtual_paths_deep(block)
                if rewritten != block:
                    changed = True
                updated_blocks.append(rewritten)
                continue

            migrated = _bump_storage_version(block)
            migrated = _rewrite_virtual_paths_deep(migrated)
            if migrated != block:
                changed = True
            updated_blocks.append(migrated)

        if not changed:
            continue
        bind.execute(
            messages.update()
            .where(messages.c.id == row["id"])
            .values(content_blocks=updated_blocks)
        )


def upgrade() -> None:
    _migrate_all_user_data()
    _migrate_message_content_blocks()


def downgrade() -> None:
    raise NotImplementedError("user_data v4 migration is irreversible")

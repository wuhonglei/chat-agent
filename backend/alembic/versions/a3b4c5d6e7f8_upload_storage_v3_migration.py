"""上传目录 v3：kb content_id 重命名、附件搬迁、删除 attachment 表

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-05-23

"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORAGE_VERSION_V3 = 3
CHAT_ATTACHMENT_PREVIEW_PREFIX = "/api/file/preview"


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return inspector.has_table(table_name)


def _rename_kb_file_id_to_content_id() -> None:
    if not _has_table("kb_file_chunk_embeddings"):
        return
    if _has_column("kb_file_chunk_embeddings", "content_id"):
        return
    if not _has_column("kb_file_chunk_embeddings", "file_id"):
        return

    op.alter_column(
        "kb_file_chunk_embeddings",
        "file_id",
        new_column_name="content_id",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_kb_file_chunk_embeddings_file_id "
        "RENAME TO ix_kb_file_chunk_embeddings_content_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_kb_file_chunk_embeddings_user_file "
        "RENAME TO ix_kb_file_chunk_embeddings_user_content"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_kb_file_chunk_embeddings_user_file_chunk_idx'
            ) THEN
                ALTER TABLE kb_file_chunk_embeddings
                RENAME CONSTRAINT uq_kb_file_chunk_embeddings_user_file_chunk_idx
                TO uq_kb_file_chunk_embeddings_user_content_chunk_idx;
            END IF;
        END $$;
        """
    )


def _infer_v2_storage_key(block: dict[str, Any]) -> str | None:
    storage_key = block.get("storage_key")
    if isinstance(storage_key, str) and storage_key.strip():
        return storage_key.strip()
    content_id = block.get("id")
    if not isinstance(content_id, str) or not content_id:
        return None
    block_type = block.get("type")
    mime = str(block.get("mime") or "").lower()
    if block_type == "pdf" or mime == "application/pdf":
        return f"raw/{content_id}.pdf"
    if block_type == "markdown" or mime == "text/markdown":
        return f"raw/{content_id}.md"
    if block_type == "image" or mime.startswith("image/"):
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            if mime.endswith(ext.lstrip(".")) or ext in mime:
                return f"raw/{content_id}{ext}"
        return f"raw/{content_id}.jpg"
    return None


def _allocate_display_name(used: set[str], raw_name: str, fallback: str) -> str:
    base_name = (raw_name or "").strip() or fallback
    if base_name not in used:
        used.add(base_name)
        return base_name
    stem = Path(base_name).stem
    ext = Path(base_name).suffix
    counter = 1
    while True:
        candidate = f"{stem}({counter}){ext}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


def _copy_file_if_needed(src: Path, dest: Path) -> None:
    if dest.is_file():
        if src.is_file() and dest.stat().st_size == src.stat().st_size:
            return
        return
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _migrate_attachment_block(
    *,
    block: dict[str, Any],
    user_id: str,
    conversation_id: str,
    uploads_root: Path,
    used_names: set[str],
) -> dict[str, Any]:
    if block.get("storage_version") == STORAGE_VERSION_V3:
        return block

    block_type = block.get("type")
    if block_type not in {"image", "pdf", "markdown"}:
        return block

    old_key = _infer_v2_storage_key(block)
    if old_key is None:
        return block

    ext = Path(old_key).suffix or ".bin"
    default_stem = "document"
    if block_type == "image":
        default_stem = "image"
    display_name = _allocate_display_name(
        used_names,
        str(block.get("name") or ""),
        f"{default_stem}{ext}",
    )
    new_key = f"{conversation_id}/{display_name}"
    src = uploads_root / old_key
    dest = uploads_root / conversation_id / display_name
    _copy_file_if_needed(src, dest)

    updated = dict(block)
    updated["storage_key"] = new_key
    updated["url"] = f"{CHAT_ATTACHMENT_PREVIEW_PREFIX}/{user_id}/{new_key}"
    updated["storage_version"] = STORAGE_VERSION_V3
    updated["name"] = display_name

    if block_type == "pdf" and isinstance(block.get("markdown"), dict):
        md_block = dict(block["markdown"])
        md_old_key = _infer_v2_storage_key(md_block)
        md_stem = Path(display_name).stem
        md_display = f"{md_stem}.md"
        md_new_key = f"{conversation_id}/derived/{md_display}"
        if md_old_key:
            md_src = uploads_root / md_old_key
            md_dest = uploads_root / conversation_id / "derived" / md_display
            _copy_file_if_needed(md_src, md_dest)
        md_block["storage_key"] = md_new_key
        md_block["url"] = f"{CHAT_ATTACHMENT_PREVIEW_PREFIX}/{user_id}/{md_new_key}"
        md_block["storage_version"] = STORAGE_VERSION_V3
        md_block["name"] = md_display
        updated["markdown"] = md_block

    return updated


def _migrate_messages_content_blocks() -> None:
    bind = op.get_bind()
    messages = sa.table(
        "messages",
        sa.column("id", sa.String()),
        sa.column("conversation_id", sa.String()),
        sa.column("content_blocks", sa.JSON()),
    )
    conversations = sa.table(
        "conversations",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.String()),
    )

    rows = bind.execute(
        sa.select(
            messages.c.id,
            messages.c.conversation_id,
            messages.c.content_blocks,
            conversations.c.user_id,
        )
        .select_from(
            messages.join(
                conversations,
                messages.c.conversation_id == conversations.c.id,
            )
        )
        .where(messages.c.content_blocks.is_not(None))
    ).mappings()

    for row in rows:
        content_blocks = row["content_blocks"]
        if not isinstance(content_blocks, list):
            continue

        user_id = str(row["user_id"])
        conversation_id = str(row["conversation_id"])
        uploads_root = _BACKEND_ROOT / "data" / "user_data" / user_id / "uploads"
        used_names: set[str] = set()

        updated_blocks: list[Any] = []
        changed = False
        for block in content_blocks:
            if not isinstance(block, dict):
                updated_blocks.append(block)
                continue
            migrated = _migrate_attachment_block(
                block=block,
                user_id=user_id,
                conversation_id=conversation_id,
                uploads_root=uploads_root,
                used_names=used_names,
            )
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


def _drop_attachment_tables() -> None:
    if _has_table("conversation_attachments"):
        op.drop_table("conversation_attachments")
    if _has_table("attachment_files"):
        op.drop_table("attachment_files")


def upgrade() -> None:
    _rename_kb_file_id_to_content_id()
    _migrate_messages_content_blocks()
    _drop_attachment_tables()


def downgrade() -> None:
    raise NotImplementedError("upload storage v3 migration is irreversible")

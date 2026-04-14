"""迁移历史消息中的旧附件预览 URL

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-04-14

"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None

OLD_PREVIEW_PREFIX = "/api/file/image/preview/"
NEW_PREVIEW_PREFIX = "/api/file/preview/"


def _rewrite_preview_prefix(
    content_blocks: Any,
    *,
    source_prefix: str,
    target_prefix: str,
) -> Any:
    if not isinstance(content_blocks, list):
        return content_blocks

    updated_blocks: list[Any] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            updated_blocks.append(block)
            continue

        updated_block = dict(block)
        block_type = updated_block.get("type")
        url = updated_block.get("url")
        if (
            block_type in {"image", "pdf"}
            and isinstance(url, str)
            and url.startswith(source_prefix)
        ):
            updated_block["url"] = f"{target_prefix}{url[len(source_prefix) :]}"
        updated_blocks.append(updated_block)
    return updated_blocks


def _migrate_preview_urls(*, source_prefix: str, target_prefix: str) -> None:
    bind = op.get_bind()
    messages = sa.table(
        "messages",
        sa.column("id", sa.String()),
        sa.column("content_blocks", sa.JSON()),
    )

    rows = (
        bind.execute(
            sa.select(messages.c.id, messages.c.content_blocks).where(
                messages.c.content_blocks.is_not(None)
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        content_blocks = row["content_blocks"]
        updated_blocks = _rewrite_preview_prefix(
            content_blocks,
            source_prefix=source_prefix,
            target_prefix=target_prefix,
        )
        if updated_blocks == content_blocks:
            continue
        bind.execute(
            messages.update()
            .where(messages.c.id == row["id"])
            .values(content_blocks=updated_blocks)
        )


def upgrade() -> None:
    _migrate_preview_urls(
        source_prefix=OLD_PREVIEW_PREFIX,
        target_prefix=NEW_PREVIEW_PREFIX,
    )


def downgrade() -> None:
    _migrate_preview_urls(
        source_prefix=NEW_PREVIEW_PREFIX,
        target_prefix=OLD_PREVIEW_PREFIX,
    )

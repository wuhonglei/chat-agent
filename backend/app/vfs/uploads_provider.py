"""Uploads virtual file provider based on conversation_attachments table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment_file_db import AttachmentFileDb
from app.models.conversation_attachment_db import ConversationAttachmentDb
from app.vfs.config import vfs_config


@dataclass
class VirtualFileEntry:
    """A virtual file entry in /uploads/ directory."""

    display_name: str
    storage_key: str
    mime: str | None
    size: int
    kind: str | None
    virtual_path: str


class UploadsProvider:
    """Provide virtual file listing for /uploads/ directory."""

    FORBIDDEN_CHARS = {"/", "..", "\\", "\x00"}

    async def list_virtual_files(
        self,
        user_id: str,
        workspace_id: str,
        db: AsyncSession,
    ) -> list[VirtualFileEntry]:
        """List virtual files in /uploads/ for current conversation.

        Queries conversation_attachments joined with attachment_files.
        Handles duplicate display names by appending (1), (2), etc.
        """
        attachment_file_id_column = cast(
            Any, ConversationAttachmentDb.attachment_file_id
        )
        conversation_id_column = cast(Any, ConversationAttachmentDb.conversation_id)
        user_id_column = cast(Any, ConversationAttachmentDb.user_id)
        created_at_column = cast(Any, ConversationAttachmentDb.created_at)

        # Query attachments for this conversation
        stmt = (
            select(AttachmentFileDb)
            .join(
                ConversationAttachmentDb,
                attachment_file_id_column == AttachmentFileDb.id,
            )
            .where(
                conversation_id_column == workspace_id,
                user_id_column == user_id,
            )
            .order_by(asc(created_at_column))
        )

        result = await db.execute(stmt)
        rows = result.scalars().all()

        # Handle duplicate display names
        name_count: dict[str, int] = {}
        entries: list[VirtualFileEntry] = []

        for attachment in rows:
            display_name = attachment.display_name

            # Validate display name
            self._validate_display_name(display_name)

            # Handle duplicates
            if display_name in name_count:
                name_count[display_name] += 1
                base = Path(display_name).stem
                ext = Path(display_name).suffix
                display_name = f"{base}({name_count[display_name]}){ext}"
            else:
                name_count[display_name] = 0

            virtual_path = f"{vfs_config.uploads_prefix}{display_name}"

            entries.append(
                VirtualFileEntry(
                    display_name=display_name,
                    storage_key=attachment.storage_key,
                    mime=attachment.mime,
                    size=attachment.size,
                    kind=attachment.kind,
                    virtual_path=virtual_path,
                )
            )

        return entries

    def _validate_display_name(self, name: str) -> None:
        """Validate display name for security."""
        if not name or not name.strip():
            raise ValueError("Display name cannot be empty")

        for char in self.FORBIDDEN_CHARS:
            if char in name:
                raise ValueError(f"Display name contains forbidden character: {char}")

        # Check for control characters
        if any(ord(c) < 32 for c in name):
            raise ValueError("Display name contains control characters")

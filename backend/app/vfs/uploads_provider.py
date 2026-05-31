"""Uploads virtual file provider based on filesystem scan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.chat_upload.attachment import (
    build_conversation_storage_key,
    build_derived_markdown_storage_key,
    get_conversation_upload_dir,
    media_type_for_preview,
)
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
    """Provide virtual file listing for /uploads/ by scanning conversation directory."""

    FORBIDDEN_CHARS = {"/", "..", "\\", "\x00"}

    async def list_virtual_files(
        self,
        user_id: str,
        conversation_id: str,
        db: object = None,
    ) -> list[VirtualFileEntry]:
        """List virtual files in /uploads/ for current conversation."""
        _ = db
        upload_dir = get_conversation_upload_dir(user_id, conversation_id)
        entries: list[VirtualFileEntry] = []

        if not upload_dir.is_dir():
            return entries

        for child in sorted(upload_dir.iterdir(), key=lambda p: p.name):
            if child.name == "derived":
                continue
            if child.is_file():
                entries.append(
                    self._entry_from_file(user_id, conversation_id, child.name)
                )

        derived_dir = upload_dir / "derived"
        if derived_dir.is_dir():
            for child in sorted(derived_dir.iterdir(), key=lambda p: p.name):
                if child.is_file() and child.suffix.lower() == ".md":
                    entries.append(
                        self._entry_from_derived(
                            user_id, conversation_id, child.name, child
                        )
                    )

        return entries

    def _entry_from_file(
        self, user_id: str, conversation_id: str, filename: str
    ) -> VirtualFileEntry:
        self._validate_display_name(filename)
        storage_key = build_conversation_storage_key(conversation_id, filename)
        upload_dir = get_conversation_upload_dir(user_id, conversation_id)
        path = upload_dir / filename
        size = path.stat().st_size if path.is_file() else 0
        mime = media_type_for_preview(filename)
        kind = "derived" if filename.endswith(".md") else "raw"
        return VirtualFileEntry(
            display_name=filename,
            storage_key=storage_key,
            mime=mime,
            size=size,
            kind=kind,
            virtual_path=f"{vfs_config.uploads_prefix}{filename}",
        )

    def _entry_from_derived(
        self,
        user_id: str,
        conversation_id: str,
        filename: str,
        path: Path,
    ) -> VirtualFileEntry:
        self._validate_display_name(filename)
        storage_key = build_derived_markdown_storage_key(conversation_id, filename)
        size = path.stat().st_size if path.is_file() else 0
        return VirtualFileEntry(
            display_name=filename,
            storage_key=storage_key,
            mime="text/markdown",
            size=size,
            kind="derived",
            virtual_path=f"{vfs_config.uploads_prefix}derived/{filename}",
        )

    def _validate_display_name(self, name: str) -> None:
        """Validate display name for security."""
        if not name or not name.strip():
            raise ValueError("Display name cannot be empty")

        for char in self.FORBIDDEN_CHARS:
            if char in name:
                raise ValueError(f"Display name contains forbidden character: {char}")

        if any(ord(c) < 32 for c in name):
            raise ValueError("Display name contains control characters")

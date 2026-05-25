"""File MCP utilities for path resolution and quota checking."""

from __future__ import annotations

from pathlib import Path

from app.utils.workspace import ensure_write_quota, truncate_content
from app.vfs.paths import get_paths
from app.vfs.resolver import PathPermission, PathResolver

__all__ = [
    "ensure_write_quota",
    "get_uploads_dir",
    "resolve_virtual_path",
    "truncate_content",
]


def get_uploads_dir(user_id: str, conversation_id: str) -> Path:
    """Get conversation uploads directory."""
    paths = get_paths()
    return paths.sandbox_uploads_dir(
        paths.validate_user_id(user_id),
        paths.validate_conversation_id(conversation_id),
    )


def resolve_virtual_path(
    virtual_path: str,
    user_id: str,
    conversation_id: str,
    permission: PathPermission = PathPermission.READ_WRITE,
) -> Path:
    """Resolve virtual path to physical path."""
    resolver = PathResolver()
    physical_path, resolved_permission = resolver.resolve_virtual_to_physical(
        virtual_path, user_id, conversation_id
    )

    if (
        permission == PathPermission.READ_WRITE
        and resolved_permission == PathPermission.READ_ONLY
    ):
        raise ValueError(
            f"Write operation not allowed on read-only path: {virtual_path}"
        )

    if not physical_path.exists():
        raise ValueError(f"Path does not exist: {virtual_path}")

    return physical_path

"""Virtual path mapper for bidirectional path translation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.vfs.config import SKILLS_ROOT, USER_DATA_ROOT, vfs_config
from app.vfs.resolver import PathPermission, PathResolver


@dataclass
class MappingContext:
    """Context for path mapping operations."""

    user_id: str
    workspace_id: str


class VirtualPathMapper:
    """Bidirectional mapper: virtual path <-> physical path."""

    def __init__(self) -> None:
        self._resolver = PathResolver()

    def to_virtual(self, physical: Path, ctx: MappingContext) -> str:
        """Convert physical path to virtual path (for API responses)."""
        physical_resolved = physical.resolve()

        # Check workspace
        workspace_root = (
            USER_DATA_ROOT / ctx.user_id / "workspaces" / ctx.workspace_id
        ).resolve()
        if str(physical_resolved).startswith(str(workspace_root)):
            relative = physical_resolved.relative_to(workspace_root)
            if str(relative) == ".":
                return vfs_config.workspace_prefix.rstrip("/")
            return f"{vfs_config.workspace_prefix}{relative.as_posix()}"

        # Check uploads
        uploads_root = (USER_DATA_ROOT / ctx.user_id / "uploads").resolve()
        if str(physical_resolved).startswith(str(uploads_root)):
            relative = physical_resolved.relative_to(uploads_root)
            if str(relative) == ".":
                return vfs_config.uploads_prefix.rstrip("/")
            return f"{vfs_config.uploads_prefix}{relative.as_posix()}"

        # Check skills
        skills_root = SKILLS_ROOT.resolve()
        if str(physical_resolved).startswith(str(skills_root)):
            relative = physical_resolved.relative_to(skills_root)
            if str(relative) == ".":
                return vfs_config.skills_prefix.rstrip("/")
            return f"{vfs_config.skills_prefix}{relative.as_posix()}"

        # Fallback: return as-is (should not happen in normal flow)
        return str(physical_resolved)

    def to_physical(self, virtual: str, ctx: MappingContext) -> Path:
        """Convert virtual path to physical path (for actual operations)."""
        physical, _ = self._resolver.resolve_virtual_to_physical(
            virtual, ctx.user_id, ctx.workspace_id
        )
        return physical

    def resolve_permission(self, virtual: str) -> PathPermission:
        """Return the permission level for a virtual path."""
        if virtual.startswith(vfs_config.workspace_prefix):
            return PathPermission.READ_WRITE
        elif virtual.startswith(vfs_config.uploads_prefix):
            return PathPermission.READ_ONLY
        elif virtual.startswith(vfs_config.skills_prefix):
            return PathPermission.READ_ONLY
        return PathPermission.FORBIDDEN

    def sanitize_response(self, data: Any, ctx: MappingContext) -> Any:
        """Recursively replace physical paths with virtual paths in response data."""
        if isinstance(data, str):
            # Try to detect and replace physical paths
            return self._replace_physical_paths(data, ctx)
        elif isinstance(data, dict):
            return {k: self.sanitize_response(v, ctx) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_response(item, ctx) for item in data]
        return data

    def _replace_physical_paths(self, text: str, ctx: MappingContext) -> str:
        """Replace known physical path patterns with virtual paths."""
        # Replace workspace paths
        workspace_root = str(
            (USER_DATA_ROOT / ctx.user_id / "workspaces" / ctx.workspace_id).resolve()
        )
        if workspace_root in text:
            text = text.replace(workspace_root, vfs_config.workspace_prefix.rstrip("/"))

        # Replace uploads paths
        uploads_root = str((USER_DATA_ROOT / ctx.user_id / "uploads").resolve())
        if uploads_root in text:
            text = text.replace(uploads_root, vfs_config.uploads_prefix.rstrip("/"))

        # Replace skills paths
        skills_root = str(SKILLS_ROOT.resolve())
        if skills_root in text:
            text = text.replace(skills_root, vfs_config.skills_prefix.rstrip("/"))

        return text

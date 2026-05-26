"""Virtual path mapper for bidirectional path translation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.vfs.config import SKILLS_ROOT, vfs_config
from app.vfs.paths import get_paths
from app.vfs.resolver import PathPermission, PathResolver


@dataclass
class MappingContext:
    """Context for path mapping operations."""

    user_id: str
    conversation_id: str


class VirtualPathMapper:
    """Bidirectional mapper: virtual path <-> physical path."""

    def __init__(self) -> None:
        self._resolver = PathResolver()

    def to_virtual(self, physical: Path, ctx: MappingContext) -> str:
        """Convert physical path to virtual path (for API responses)."""
        physical_resolved = physical.resolve()
        paths = get_paths()

        workspace_root = paths.sandbox_work_dir(
            ctx.user_id, ctx.conversation_id
        ).resolve()
        if str(physical_resolved).startswith(str(workspace_root)):
            relative = physical_resolved.relative_to(workspace_root)
            if str(relative) == ".":
                return vfs_config.workspace_prefix.rstrip("/")
            return f"{vfs_config.workspace_prefix}{relative.as_posix()}"

        uploads_root = paths.sandbox_uploads_dir(
            ctx.user_id, ctx.conversation_id
        ).resolve()
        if str(physical_resolved).startswith(str(uploads_root)):
            relative = physical_resolved.relative_to(uploads_root)
            if str(relative) == ".":
                return vfs_config.uploads_prefix.rstrip("/")
            return f"{vfs_config.uploads_prefix}{relative.as_posix()}"

        outputs_root = paths.sandbox_outputs_dir(
            ctx.user_id, ctx.conversation_id
        ).resolve()
        if str(physical_resolved).startswith(str(outputs_root)):
            relative = physical_resolved.relative_to(outputs_root)
            if str(relative) == ".":
                return vfs_config.outputs_prefix.rstrip("/")
            return f"{vfs_config.outputs_prefix}{relative.as_posix()}"

        user_skills_root = paths.user_skills_dir(ctx.user_id).resolve()
        if str(physical_resolved).startswith(str(user_skills_root)):
            relative = physical_resolved.relative_to(user_skills_root)
            if str(relative) == ".":
                return vfs_config.skills_custom_prefix.rstrip("/")
            return f"{vfs_config.skills_custom_prefix}{relative.as_posix()}"

        skills_root = SKILLS_ROOT.resolve()
        if str(physical_resolved).startswith(str(skills_root)):
            relative = physical_resolved.relative_to(skills_root)
            if str(relative) == ".":
                return vfs_config.skills_prefix.rstrip("/")
            return f"{vfs_config.skills_prefix}{relative.as_posix()}"

        return str(physical_resolved)

    def to_physical(self, virtual: str, ctx: MappingContext) -> Path:
        """Convert virtual path to physical path (for actual operations)."""
        physical, _ = self._resolver.resolve_virtual_to_physical(
            virtual, ctx.user_id, ctx.conversation_id
        )
        return physical

    def resolve_permission(self, virtual: str) -> PathPermission:
        """Return the permission level for a virtual path."""
        if virtual.startswith(vfs_config.workspace_prefix):
            return PathPermission.READ_WRITE
        if virtual.startswith(vfs_config.outputs_prefix):
            return PathPermission.READ_WRITE
        if virtual.startswith(vfs_config.uploads_prefix):
            return PathPermission.READ_ONLY
        if virtual.startswith(vfs_config.skills_custom_prefix):
            return PathPermission.READ_WRITE
        if virtual.startswith(vfs_config.skills_prefix):
            return PathPermission.READ_ONLY
        return PathPermission.FORBIDDEN

    def mask_paths_in_text(self, text: str, ctx: MappingContext) -> str:
        """Replace known physical path patterns with virtual paths in plain text."""
        return self._replace_physical_paths(text, ctx)

    def sanitize_response(self, data: Any, ctx: MappingContext) -> Any:
        """Recursively replace physical paths with virtual paths in response data."""
        if isinstance(data, str):
            return self.mask_paths_in_text(data, ctx)
        if isinstance(data, dict):
            return {k: self.sanitize_response(v, ctx) for k, v in data.items()}
        if isinstance(data, list):
            return [self.sanitize_response(item, ctx) for item in data]
        return data

    def _replace_physical_paths(self, text: str, ctx: MappingContext) -> str:
        """Replace known physical path patterns with virtual paths."""
        paths = get_paths()
        replacements = (
            (
                str(paths.sandbox_work_dir(ctx.user_id, ctx.conversation_id).resolve()),
                vfs_config.workspace_prefix.rstrip("/"),
            ),
            (
                str(
                    paths.sandbox_uploads_dir(
                        ctx.user_id, ctx.conversation_id
                    ).resolve()
                ),
                vfs_config.uploads_prefix.rstrip("/"),
            ),
            (
                str(
                    paths.sandbox_outputs_dir(
                        ctx.user_id, ctx.conversation_id
                    ).resolve()
                ),
                vfs_config.outputs_prefix.rstrip("/"),
            ),
            (
                str(paths.user_skills_dir(ctx.user_id).resolve()),
                vfs_config.skills_custom_prefix.rstrip("/"),
            ),
            (str(SKILLS_ROOT.resolve()), vfs_config.skills_prefix.rstrip("/")),
        )
        for physical, virtual in replacements:
            if physical in text:
                text = text.replace(physical, virtual)
        return text

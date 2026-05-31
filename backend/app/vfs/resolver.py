"""Path resolver with security validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from app.vfs.config import SKILLS_ROOT, vfs_config
from app.vfs.paths import SKILLS_PUBLIC_DIR, get_paths

FORBIDDEN_SEGMENTS = frozenset(
    {
        ".git",
        ".ssh",
        ".aws",
        ".cursor",
        "__pycache__",
        ".env",
    }
)


def resolve_relative_under_root(root: Path, relative_path: str) -> tuple[Path, Path]:
    """Resolve a relative path under *root* (HTTP workspace API, skills paths)."""
    root = root.resolve()
    relative = (relative_path or "").strip()
    if not relative:
        return root, root
    if Path(relative).is_absolute():
        raise ValueError("absolute path is not allowed")

    normalized_parts = [part for part in Path(relative).parts if part not in ("", ".")]
    if not normalized_parts:
        return root, root
    for part in normalized_parts:
        if part == ".." or part.lower() in FORBIDDEN_SEGMENTS:
            raise ValueError("forbidden path")

    target = (root / Path(*normalized_parts)).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path escapes workspace")
    return root, target


class PathPermission(Enum):
    """Path permission levels."""

    READ_WRITE = "read_write"
    READ_ONLY = "read_only"
    FORBIDDEN = "forbidden"


class PathResolver:
    """Resolve virtual paths to physical paths with security checks."""

    FORBIDDEN_SEGMENTS = FORBIDDEN_SEGMENTS

    def resolve_virtual_to_physical(
        self,
        virtual_path: str,
        user_id: str,
        conversation_id: str,
    ) -> tuple[Path, PathPermission]:
        """Resolve virtual path to physical path with permission check."""
        virtual_path = virtual_path.strip()
        paths = get_paths()

        if virtual_path.startswith(vfs_config.workspace_prefix):
            base_dir = paths.sandbox_work_dir(user_id, conversation_id)
            relative_part = virtual_path[len(vfs_config.workspace_prefix) :]
            permission = PathPermission.READ_WRITE
        elif virtual_path.startswith(vfs_config.uploads_prefix):
            base_dir = paths.sandbox_uploads_dir(user_id, conversation_id)
            relative_part = virtual_path[len(vfs_config.uploads_prefix) :]
            permission = PathPermission.READ_ONLY
        elif virtual_path.startswith(vfs_config.outputs_prefix):
            base_dir = paths.sandbox_outputs_dir(user_id, conversation_id)
            relative_part = virtual_path[len(vfs_config.outputs_prefix) :]
            permission = PathPermission.READ_WRITE
        elif virtual_path.startswith(vfs_config.skills_custom_prefix):
            base_dir = paths.user_skills_dir(user_id)
            relative_part = virtual_path[len(vfs_config.skills_custom_prefix) :]
            permission = PathPermission.READ_WRITE
        elif virtual_path.startswith(vfs_config.skills_public_prefix):
            base_dir = SKILLS_PUBLIC_DIR
            relative_part = virtual_path[len(vfs_config.skills_public_prefix) :]
            permission = PathPermission.READ_ONLY
        elif virtual_path.startswith(vfs_config.skills_prefix):
            base_dir = SKILLS_ROOT
            relative_part = virtual_path[len(vfs_config.skills_prefix) :]
            permission = PathPermission.READ_ONLY
        else:
            raise ValueError(
                f"Invalid virtual path prefix. Must start with "
                f"{vfs_config.workspace_prefix}, {vfs_config.uploads_prefix}, "
                f"{vfs_config.outputs_prefix}, {vfs_config.skills_custom_prefix}, "
                f"{vfs_config.skills_public_prefix}, or {vfs_config.skills_prefix}"
            )

        base_dir = base_dir.resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        if not relative_part or relative_part == "/":
            return base_dir, permission

        self._validate_relative_path(relative_part)

        physical_path = (base_dir / relative_part).resolve()

        if not str(physical_path).startswith(str(base_dir)):
            raise ValueError("Path traversal detected: path escapes root directory")

        return physical_path, permission

    def _validate_relative_path(self, relative_path: str) -> None:
        """Validate relative path for security issues."""
        if not relative_path:
            return

        if Path(relative_path).is_absolute():
            raise ValueError("Absolute path not allowed in virtual path")

        parts = Path(relative_path).parts
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                raise ValueError("Path traversal (..) not allowed")
            if part.lower() in self.FORBIDDEN_SEGMENTS:
                raise ValueError(f"Forbidden directory segment: {part}")

    def get_virtual_prefix_for_permission(self, permission: PathPermission) -> str:
        """Get the virtual path prefix for a given permission type."""
        if permission == PathPermission.READ_WRITE:
            return vfs_config.workspace_prefix
        if permission == PathPermission.READ_ONLY:
            return vfs_config.uploads_prefix
        return ""

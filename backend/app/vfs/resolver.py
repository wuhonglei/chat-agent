"""Path resolver with security validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from app.vfs.config import SKILLS_ROOT, USER_DATA_ROOT, vfs_config


class PathPermission(Enum):
    """Path permission levels."""

    READ_WRITE = "read_write"
    READ_ONLY = "read_only"
    FORBIDDEN = "forbidden"


class PathResolver:
    """Resolve virtual paths to physical paths with security checks."""

    FORBIDDEN_SEGMENTS = {
        ".git",
        ".ssh",
        ".aws",
        ".cursor",
        "__pycache__",
        ".env",
    }

    def resolve_virtual_to_physical(
        self,
        virtual_path: str,
        user_id: str,
        workspace_id: str,
    ) -> tuple[Path, PathPermission]:
        """Resolve virtual path to physical path with permission check.

        Returns:
            Tuple of (physical_path, permission_level)

        Raises:
            ValueError: If path is invalid or forbidden
        """
        virtual_path = virtual_path.strip()

        # Determine prefix and get base directory
        if virtual_path.startswith(vfs_config.workspace_prefix):
            base_dir = self._get_workspace_root(user_id, workspace_id)
            relative_part = virtual_path[len(vfs_config.workspace_prefix) :]
            permission = PathPermission.READ_WRITE
        elif virtual_path.startswith(vfs_config.uploads_prefix):
            base_dir = self._get_uploads_root(user_id, workspace_id)
            relative_part = virtual_path[len(vfs_config.uploads_prefix) :]
            permission = PathPermission.READ_ONLY
        elif virtual_path.startswith(vfs_config.skills_prefix):
            base_dir = SKILLS_ROOT
            relative_part = virtual_path[len(vfs_config.skills_prefix) :]
            permission = PathPermission.READ_ONLY
        else:
            raise ValueError(
                f"Invalid virtual path prefix. Must start with "
                f"{vfs_config.workspace_prefix}, {vfs_config.uploads_prefix}, "
                f"or {vfs_config.skills_prefix}"
            )

        # Resolve the physical path
        if not relative_part or relative_part == "/":
            return base_dir, permission

        # Security checks on relative path
        self._validate_relative_path(relative_part)

        # Build and resolve physical path
        physical_path = (base_dir / relative_part).resolve()

        # Ensure resolved path is still under base directory
        if not str(physical_path).startswith(str(base_dir.resolve())):
            raise ValueError("Path traversal detected: path escapes root directory")

        return physical_path, permission

    def _validate_relative_path(self, relative_path: str) -> None:
        """Validate relative path for security issues."""
        if not relative_path:
            return

        # Check for absolute path
        if Path(relative_path).is_absolute():
            raise ValueError("Absolute path not allowed in virtual path")

        # Check each segment
        parts = Path(relative_path).parts
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                raise ValueError("Path traversal (..) not allowed")
            if part.lower() in self.FORBIDDEN_SEGMENTS:
                raise ValueError(f"Forbidden directory segment: {part}")

    def _get_workspace_root(self, user_id: str, workspace_id: str) -> Path:
        """Get workspace root directory."""
        safe_user_id = self._validate_id(user_id)
        safe_workspace_id = self._validate_id(workspace_id)
        root = USER_DATA_ROOT / safe_user_id / "workspaces" / safe_workspace_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _get_uploads_root(self, user_id: str, workspace_id: str) -> Path:
        """Get conversation-scoped uploads root directory."""
        safe_user_id = self._validate_id(user_id)
        safe_workspace_id = self._validate_id(workspace_id)
        root = USER_DATA_ROOT / safe_user_id / "uploads" / safe_workspace_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _validate_id(value: str) -> str:
        """Validate user_id or workspace_id."""
        normalized = (value or "").strip()
        if (
            not normalized
            or "/" in normalized
            or "\\" in normalized
            or ".." in normalized
            or normalized.startswith(".")
        ):
            raise ValueError("Invalid ID: contains forbidden characters")
        return normalized

    def get_virtual_prefix_for_permission(self, permission: PathPermission) -> str:
        """Get the virtual path prefix for a given permission type."""
        if permission == PathPermission.READ_WRITE:
            return vfs_config.workspace_prefix
        elif permission == PathPermission.READ_ONLY:
            return vfs_config.uploads_prefix
        return ""

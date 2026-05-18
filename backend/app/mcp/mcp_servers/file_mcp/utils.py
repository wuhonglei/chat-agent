"""File MCP utilities for path resolution and quota checking."""

from __future__ import annotations

from pathlib import Path

from app.vfs.config import USER_DATA_ROOT
from app.vfs.resolver import PathPermission, PathResolver


def get_workspace_root(user_id: str, workspace_id: str) -> Path:
    """Get workspace root directory."""
    safe_user_id = _validate_id(user_id)
    safe_workspace_id = _validate_id(workspace_id)
    root = USER_DATA_ROOT / safe_user_id / "workspaces" / safe_workspace_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_uploads_root(user_id: str) -> Path:
    """Get uploads root directory."""
    safe_user_id = _validate_id(user_id)
    root = USER_DATA_ROOT / safe_user_id / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


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


def resolve_virtual_path(
    virtual_path: str,
    user_id: str,
    workspace_id: str,
    permission: PathPermission = PathPermission.READ_WRITE,
) -> Path:
    """Resolve virtual path to physical path.

    Args:
        virtual_path: Virtual path (e.g., /workspace/src/main.py)
        user_id: Current user ID
        workspace_id: Current workspace ID
        permission: Required permission level

    Returns:
        Physical path

    Raises:
        ValueError: If path is invalid or permission denied
    """
    resolver = PathResolver()
    physical_path, resolved_permission = resolver.resolve_virtual_to_physical(
        virtual_path, user_id, workspace_id
    )

    # Check permission
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


def ensure_write_quota(root: Path, target: Path, content: str) -> None:
    """Check write quota before writing file."""
    max_workspace_bytes = 2000 * 1024 * 1024  # 2GB

    # Calculate current usage
    total_bytes = 0
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file():
                total_bytes += path.stat().st_size

    # Calculate new size
    new_size = len(content.encode("utf-8"))
    old_size = target.stat().st_size if target.exists() and target.is_file() else 0
    next_total = total_bytes - old_size + new_size

    if next_total > max_workspace_bytes:
        raise ValueError(
            f"Workspace quota exceeded ({max_workspace_bytes} bytes). "
            "Please delete files first."
        )


def truncate_content(content: str, limit: int = 200000) -> tuple[str, bool]:
    """Truncate content to limit."""
    if len(content) <= limit:
        return content, False
    return content[:limit], True

"""Workspace utility functions for path validation and quota management."""

from __future__ import annotations

from pathlib import Path

from app.agent_skills.registry import SKILLS_DIR

FORBIDDEN_SEGMENTS = {
    ".git",
    ".ssh",
    ".aws",
    ".cursor",
    "__pycache__",
    ".env",
}

MAX_WORKSPACE_BYTES = 2000 * 1024 * 1024
MAX_READ_CHARS = 200_000

BACKEND_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_ROOT = BACKEND_ROOT / "data" / "user_data"


def validate_user_id(user_id: str) -> str:
    """Validate and normalize user_id."""
    normalized = (user_id or "").strip()
    if (
        not normalized
        or "/" in normalized
        or "\\" in normalized
        or ".." in normalized
        or normalized.startswith(".")
    ):
        raise ValueError("invalid user_id")
    return normalized


def validate_workspace_id(workspace_id: str) -> str:
    """Validate and normalize workspace_id."""
    normalized = (workspace_id or "").strip()
    if (
        not normalized
        or "/" in normalized
        or "\\" in normalized
        or ".." in normalized
        or normalized.startswith(".")
    ):
        raise ValueError("invalid workspace_id")
    return normalized


def get_workspace_root(user_id: str, workspace_id: str) -> Path:
    """Get workspace root directory, creating it if needed."""
    safe_user_id = validate_user_id(user_id)
    safe_workspace_id = validate_workspace_id(workspace_id)
    root = (USER_DATA_ROOT / safe_user_id / "workspaces" / safe_workspace_id).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_skills_root() -> Path:
    """Get skills root directory."""
    return SKILLS_DIR.resolve()


def _resolve_under_root(root: Path, relative_path: str) -> tuple[Path, Path]:
    """Resolve relative path under root with security checks."""
    relative = (relative_path or "").strip()
    if not relative:
        return root, root
    if Path(relative).is_absolute():
        raise ValueError("absolute path is not allowed")

    normalized_parts = [part for part in Path(relative).parts if part not in ("", ".")]
    if not normalized_parts:
        return root, root
    for part in normalized_parts:
        lowered = part.lower()
        if part == ".." or lowered in FORBIDDEN_SEGMENTS:
            raise ValueError("forbidden path")

    target = (root / Path(*normalized_parts)).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path escapes workspace")
    return root, target


def resolve_workspace_path(
    user_id: str, workspace_id: str, relative_path: str
) -> tuple[Path, Path]:
    """Resolve workspace relative path with security checks."""
    root = get_workspace_root(user_id, workspace_id)
    return _resolve_under_root(root, relative_path)


def resolve_skills_path(relative_path: str) -> tuple[Path, Path]:
    """Resolve skills relative path with security checks."""
    root = get_skills_root()
    return _resolve_under_root(root, relative_path)


def workspace_usage(root: Path) -> tuple[int, int]:
    """Get workspace usage statistics."""
    file_count = 0
    total_bytes = 0
    if not root.exists():
        return file_count, total_bytes
    for path in root.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
    return file_count, total_bytes


def ensure_write_quota(root: Path, *, target: Path, content: str) -> None:
    """Check write quota before writing file."""
    _, total_bytes = workspace_usage(root)
    encoded = content.encode("utf-8")
    new_size = len(encoded)

    old_size = target.stat().st_size if target.exists() and target.is_file() else 0
    next_total_bytes = total_bytes - old_size + new_size
    if next_total_bytes > MAX_WORKSPACE_BYTES:
        raise ValueError(
            f"workspace total bytes exceeds limit {MAX_WORKSPACE_BYTES}, "
            "please delete files first",
        )


def format_usage(root: Path) -> str:
    """Format workspace usage as string."""
    file_count, total_bytes = workspace_usage(root)
    return (
        f"workspace={root}, files={file_count}, "
        f"bytes={total_bytes}/{MAX_WORKSPACE_BYTES}"
    )


def truncate_content(content: str, *, limit: int = MAX_READ_CHARS) -> tuple[str, bool]:
    """Truncate content to limit."""
    if len(content) <= limit:
        return content, False
    return content[:limit], True

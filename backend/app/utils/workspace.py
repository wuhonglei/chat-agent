"""HTTP workspace API helpers: relative paths under sandbox work dir and quotas."""

from __future__ import annotations

from pathlib import Path

from app.vfs.paths import SKILLS_PUBLIC_DIR, get_paths
from app.vfs.resolver import resolve_relative_under_root

MAX_WORKSPACE_BYTES = 2000 * 1024 * 1024
MAX_READ_CHARS = 200_000


def resolve_workspace_path(
    user_id: str, conversation_id: str, relative_path: str
) -> tuple[Path, Path]:
    """Resolve workspace-relative path for /api/workspaces (not virtual /mnt/...)."""
    root = get_paths().ensure_sandbox_work_dir(user_id, conversation_id)
    return resolve_relative_under_root(root, relative_path)


def resolve_skills_path(relative_path: str) -> tuple[Path, Path]:
    """Resolve skills-relative path with security checks."""
    return resolve_relative_under_root(SKILLS_PUBLIC_DIR.resolve(), relative_path)


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

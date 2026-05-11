from __future__ import annotations

from pathlib import Path

from app.mcp.mcp_servers.agent_skills_mcp.config import (
    DANGEROUS_BASH_PATTERNS,
    FORBIDDEN_SEGMENTS,
    MAX_READ_CHARS,
    MAX_WORKSPACE_BYTES,
    USER_DATA_ROOT,
)


def validate_user_id(user_id: str) -> str:
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


def get_workspace_root(user_id: str) -> Path:
    safe_user_id = validate_user_id(user_id)
    root = (USER_DATA_ROOT / safe_user_id / "workspace").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(user_id: str, relative_path: str) -> tuple[Path, Path]:
    root = get_workspace_root(user_id)
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


def workspace_usage(root: Path) -> tuple[int, int]:
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
    file_count, total_bytes = workspace_usage(root)
    return (
        f"workspace={root}, files={file_count}, "
        f"bytes={total_bytes}/{MAX_WORKSPACE_BYTES}"
    )


def truncate_content(content: str, *, limit: int = MAX_READ_CHARS) -> tuple[str, bool]:
    if len(content) <= limit:
        return content, False
    return content[:limit], True


def ensure_safe_bash_command(command: str) -> None:
    normalized = f" {command.strip().lower()} "
    if not normalized.strip():
        raise ValueError("command is empty")
    for pattern in DANGEROUS_BASH_PATTERNS:
        if pattern in normalized:
            raise ValueError(f"dangerous command blocked: {pattern.strip()}")

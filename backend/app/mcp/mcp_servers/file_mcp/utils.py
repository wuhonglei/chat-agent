"""File MCP utilities for path resolution and quota checking."""

from __future__ import annotations

from pathlib import Path

from app.utils.workspace import ensure_write_quota, truncate_content
from app.vfs.paths import get_paths
from app.vfs.resolver import PathPermission, PathResolver

__all__ = [
    "ensure_write_quota",
    "get_uploads_dir",
    "is_probably_binary_file",
    "non_text_file_reason",
    "resolve_virtual_path",
    "truncate_content",
]

_IMAGE_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".ico",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".avif",
    }
)

# Common non-text types that produce garbage when read as UTF-8.
_BINARY_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".xlsx",
        ".xls",
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",
        ".zip",
        ".gz",
        ".tgz",
        ".tar",
        ".7z",
        ".rar",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".wav",
        ".webm",
        ".mov",
        ".avi",
        ".bin",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".sqlite",
        ".db",
    }
)

_BINARY_SNIFF_BYTES = 8192


def get_uploads_dir(user_id: str, conversation_id: str) -> Path:
    """Get conversation uploads directory."""
    paths = get_paths()
    return paths.sandbox_uploads_dir(
        paths.validate_user_id(user_id),
        paths.validate_conversation_id(conversation_id),
    )


def _looks_like_image_magic(header: bytes) -> bool:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith((b"GIF87a", b"GIF89a")):
        return True
    if header.startswith(b"BM"):
        return True
    # RIFF....WEBP
    return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"


def is_probably_binary_file(path: Path) -> bool:
    """Heuristic: NUL in the first chunk usually means non-text."""
    with path.open("rb") as f:
        chunk = f.read(_BINARY_SNIFF_BYTES)
    if not chunk:
        return False
    return b"\x00" in chunk


def non_text_file_reason(path: Path) -> str | None:
    """Return a short reason if ``path`` should not be read as text, else None."""
    suffix = path.suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _BINARY_EXTENSIONS:
        return "binary"

    try:
        with path.open("rb") as f:
            header = f.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return None

    if not header:
        return None
    if _looks_like_image_magic(header):
        return "image"
    if b"\x00" in header:
        return "binary"
    return None


def resolve_virtual_path(
    virtual_path: str,
    user_id: str,
    conversation_id: str,
    permission: PathPermission = PathPermission.READ_WRITE,
    *,
    must_exist: bool = True,
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

    if must_exist and not physical_path.exists():
        raise ValueError(f"Path does not exist: {virtual_path}")

    return physical_path

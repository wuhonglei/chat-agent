"""Virtual File System configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.vfs.paths import (
    SKILLS_PUBLIC_DIR,
    SKILLS_ROOT,
    USER_DATA_ROOT,
    VIRTUAL_PATH_PREFIX,
)

__all__ = [
    "SKILLS_PUBLIC_DIR",
    "SKILLS_ROOT",
    "USER_DATA_ROOT",
    "VFSConfig",
    "VIRTUAL_PATH_PREFIX",
    "vfs_config",
]


class VFSConfig(BaseModel):
    """Virtual File System configuration."""

    enabled: bool = Field(default=True, description="Enable virtual path mapping")
    workspace_prefix: str = Field(
        default=f"{VIRTUAL_PATH_PREFIX}/workspace/",
        description="Virtual path prefix for workspace",
    )
    uploads_prefix: str = Field(
        default=f"{VIRTUAL_PATH_PREFIX}/uploads/",
        description="Virtual path prefix for uploads",
    )
    outputs_prefix: str = Field(
        default=f"{VIRTUAL_PATH_PREFIX}/outputs/",
        description="Virtual path prefix for outputs",
    )
    skills_prefix: str = Field(
        default="/mnt/skills/",
        description="Virtual path prefix for skills",
    )
    max_file_size_mb: int = Field(default=100, description="Max single file size in MB")
    max_line_length: int = Field(
        default=2000, description="Max line length before truncation"
    )
    write_max_chars: int = Field(
        default=100000,
        description="Max characters per write operation (aligned with kimi)",
    )


vfs_config = VFSConfig()

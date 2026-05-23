"""Virtual File System configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class VFSConfig(BaseModel):
    """Virtual File System configuration."""

    enabled: bool = Field(default=True, description="Enable virtual path mapping")
    workspace_prefix: str = Field(
        default="/workspace/", description="Virtual path prefix for workspace"
    )
    uploads_prefix: str = Field(
        default="/uploads/", description="Virtual path prefix for uploads"
    )
    skills_prefix: str = Field(
        default="/skills/", description="Virtual path prefix for skills"
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

# Physical paths
BACKEND_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_ROOT = BACKEND_ROOT / "data" / "user_data"
SKILLS_ROOT = BACKEND_ROOT / "app" / "agent_skills" / "skills"

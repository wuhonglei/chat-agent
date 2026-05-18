"""Sandbox configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Global sandbox configuration."""

    enabled: bool = Field(default=True, description="Enable sandbox execution")
    backend: str = Field(
        default="docker", description="Sandbox backend: 'docker' or 'local'"
    )
    image: str = Field(default="ubuntu:22.04", description="Docker image for sandbox")
    cpu_limit: float = Field(default=1.0, description="CPU limit (number of cores)")
    memory_limit: str = Field(default="512m", description="Memory limit")
    pid_limit: int = Field(default=100, description="Max number of processes")
    timeout: int = Field(
        default=600000, description="Default timeout in milliseconds (max 600000)"
    )
    network_enabled: bool = Field(default=False, description="Enable network access")
    container_pool_size: int = Field(
        default=5, description="Container pool size for pre-warming"
    )
    output_limit: int = Field(
        default=50000, description="Max output characters before truncation"
    )


sandbox_config = SandboxConfig()

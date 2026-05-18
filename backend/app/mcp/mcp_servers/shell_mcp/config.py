"""Shell MCP configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ShellMCPConfig(BaseModel):
    """Shell MCP specific configuration."""

    max_output_chars: int = Field(
        default=50000, description="Max output characters before truncation"
    )
    default_timeout_ms: int = Field(
        default=30000, description="Default timeout in milliseconds"
    )
    max_timeout_ms: int = Field(
        default=600000, description="Maximum timeout in milliseconds (10 minutes)"
    )


shell_config = ShellMCPConfig()

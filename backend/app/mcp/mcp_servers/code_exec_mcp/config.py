from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.mcp.mcp_servers._config_utils import require_env
from app.schemas.config import MCPServerEntry

_config: CodeExecMCPConfig | None = None


class CodeExecMCPConfig(BaseModel):
    piston_base_url: str = Field(..., description="Piston API 基础地址")


class _StandaloneSettings(BaseSettings):
    piston_base_url: str = Field(..., description="Piston API 基础地址")

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


def configure(entry: MCPServerEntry) -> None:
    global _config
    _config = CodeExecMCPConfig(
        piston_base_url=require_env(entry.env, "piston_base_url"),
    )


def get_config() -> CodeExecMCPConfig:
    if _config is not None:
        return _config
    standalone = _StandaloneSettings()  # type: ignore[call-arg]
    return CodeExecMCPConfig(piston_base_url=standalone.piston_base_url)


def __getattr__(name: str) -> Any:
    if name == "config":
        return get_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

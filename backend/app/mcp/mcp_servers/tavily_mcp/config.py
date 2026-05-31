from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.mcp.mcp_servers._config_utils import require_env
from app.schemas.config import MCPServerEntry

_config: TavilyMCPConfig | None = None


class TavilyMCPConfig(BaseModel):
    tavily_api_key: str


class _StandaloneSettings(BaseSettings):
    tavily_api_key: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


def configure(entry: MCPServerEntry) -> None:
    global _config
    _config = TavilyMCPConfig(
        tavily_api_key=require_env(entry.env, "tavily_api_key"),
    )


def get_config() -> TavilyMCPConfig:
    if _config is not None:
        return _config
    standalone = _StandaloneSettings()  # type: ignore[call-arg]
    return TavilyMCPConfig(tavily_api_key=standalone.tavily_api_key)


def __getattr__(name: str) -> Any:
    if name == "config":
        return get_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

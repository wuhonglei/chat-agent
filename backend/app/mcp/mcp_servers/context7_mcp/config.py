"""Context7 MCP 配置：主应用由 registry 注入，独立运行时从 .env 读取。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.config import MCPServerEntry

_config: Context7MCPConfig | None = None


class Context7MCPConfig(BaseModel):
    url: str
    headers: dict[str, str]


class _StandaloneSettings(BaseSettings):
    url: str
    headers: dict[str, str]

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


def configure(entry: MCPServerEntry) -> None:
    global _config
    if not entry.url:
        raise ValueError("context7-mcp requires url in MCPServerEntry")
    _config = Context7MCPConfig(url=entry.url, headers=dict(entry.headers))


def get_config() -> Context7MCPConfig:
    if _config is not None:
        return _config
    standalone = _StandaloneSettings()  # type: ignore[call-arg]
    return Context7MCPConfig(url=standalone.url, headers=dict(standalone.headers))


def __getattr__(name: str) -> Any:
    if name == "config":
        return get_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.mcp.mcp_servers._config_utils import env_int, require_env
from app.schemas.config import MCPServerEntry

_config: WeatherMCPConfig | None = None


class WeatherMCPConfig(BaseModel):
    qweather_api_key: str
    qweather_base_url: str
    qweather_timeout: int = Field(default=10, ge=1)


class _StandaloneSettings(BaseSettings):
    qweather_api_key: str
    qweather_base_url: str
    qweather_timeout: int = 10

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


def configure(entry: MCPServerEntry) -> None:
    """由 MCP registry 在加载 server 模块前注入配置。"""
    global _config
    env = entry.env
    _config = WeatherMCPConfig(
        qweather_api_key=require_env(env, "qweather_api_key"),
        qweather_base_url=require_env(env, "qweather_base_url"),
        qweather_timeout=env_int(env, "qweather_timeout", 10),
    )


def get_config() -> WeatherMCPConfig:
    if _config is not None:
        return _config
    standalone = _StandaloneSettings()  # type: ignore[call-arg]
    return WeatherMCPConfig(
        qweather_api_key=standalone.qweather_api_key,
        qweather_base_url=standalone.qweather_base_url,
        qweather_timeout=standalone.qweather_timeout,
    )


def __getattr__(name: str) -> Any:
    if name == "config":
        return get_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

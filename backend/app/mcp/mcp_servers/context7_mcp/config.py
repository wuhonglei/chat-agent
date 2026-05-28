"""Context7 MCP 配置：主应用内从 settings.mcp.context7 读取，独立运行时从 .env 读取。"""

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    url: str
    headers: dict[str, str]
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


if "app.core.config" in sys.modules:
    from app.core.config import settings

    config = settings.mcp.context7_mcp
else:
    config = _Settings()  # type: ignore[assignment,call-arg]

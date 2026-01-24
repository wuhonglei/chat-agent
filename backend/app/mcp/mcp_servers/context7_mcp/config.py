"""Context7 MCP 配置：主应用内从 settings.mcp.context7 读取，独立运行时从 .env 读取。"""

import sys
from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

from app.schemas.config import MCPCacheConfig

if "app.core.config" in sys.modules:
    from app.core.config import settings

    config = settings.mcp.context7_mcp
else:

    class Settings(BaseSettings):
        url: str = Field(description="Context7 URL")
        headers: dict[str, str] = Field(description="Context7 Headers")

        cache_config: MCPCacheConfig = Field(
            default_factory=MCPCacheConfig,
            description="工具调用结果缓存配置",
        )

        model_config = ConfigDict(
            env_file=Path(__file__).parent / ".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            env_ignore_empty=True,
            extra="ignore",
        )

    config = Settings()

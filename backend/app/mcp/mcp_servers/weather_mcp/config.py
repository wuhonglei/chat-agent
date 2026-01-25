import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.config import MCPCacheConfig


class _Settings(BaseSettings):
    QWEATHER_API_KEY: str
    QWEATHER_BASE_URL: str
    QWEATHER_TIMEOUT: int = 10
    cache_config: MCPCacheConfig = Field(default_factory=MCPCacheConfig)

    model_config = SettingsConfigDict(
        # .env 文件作为可选配置源，优先从环境变量读取
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        # 允许从进程环境变量中读取配置
        extra="ignore",
    )


# 主应用内直接使用 settings.mcp.weather_mcp（含 Nacos 下发的 cache_config）；
# 独立运行时使用本文件 Settings（.env）
if "app.core.config" in sys.modules:
    from app.core.config import settings

    config = settings.mcp.weather_mcp
else:
    config = _Settings()  # type: ignore[assignment,call-arg]

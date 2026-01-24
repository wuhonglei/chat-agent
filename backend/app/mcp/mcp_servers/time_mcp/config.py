from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

from app.schemas.config import MCPCacheConfig


class Settings(BaseSettings):
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

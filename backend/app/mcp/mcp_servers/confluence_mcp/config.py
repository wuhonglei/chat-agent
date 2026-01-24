from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

from app.schemas.config import MCPCacheConfig


class Settings(BaseSettings):
    CONFLUENCE_URL: str = Field(..., description="The URL of the Confluence instance")
    CONFLUENCE_PERSONAL_TOKEN: str = Field(
        ..., description="The personal token of the Confluence instance"
    )
    CONFLUENCE_AUTH_TYPE: Literal["basic", "pat", "oauth"] = Field(
        ..., description="The authentication type of the Confluence instance"
    )
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

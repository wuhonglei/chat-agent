import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    piston_base_url: str = Field(
        ...,
        description="Piston API 基础地址",
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


# 主应用内直接使用 settings.mcp.code_exec_mcp；
# 独立运行时使用本文件 Settings（.env）
if "app.core.config" in sys.modules:
    from app.core.config import settings

    config = settings.mcp.code_exec_mcp
else:
    config = _Settings()  # type: ignore[call-arg,assignment]

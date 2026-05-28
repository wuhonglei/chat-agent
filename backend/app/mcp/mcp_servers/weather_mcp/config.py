import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    qweather_api_key: str
    qweather_base_url: str
    qweather_timeout: int = 10

    model_config = SettingsConfigDict(
        # .env 文件作为可选配置源，优先从环境变量读取
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        # 允许从进程环境变量中读取配置
        extra="ignore",
    )


# 主应用内直接使用 settings.mcp.weather_mcp；
# 独立运行时使用本文件 Settings（.env）
if "app.core.config" in sys.modules:
    from app.core.config import settings

    config = settings.mcp.weather_mcp
else:
    config = _Settings()  # type: ignore[assignment,call-arg]

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    TAVILY_API_KEY: str

    model_config = ConfigDict(
        env_file=Path(__file__).parent / '.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        env_ignore_empty=True,
        extra='ignore'
    )


# 创建配置实例
config = Settings()

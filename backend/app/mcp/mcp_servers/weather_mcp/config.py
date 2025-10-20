from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    QWEATHER_API_KEY: str
    QWEATHER_BASE_URL: str
    QWEATHER_TIMEOUT: int = 10

    @field_validator('QWEATHER_BASE_URL')
    def check_qweather_base_url(cls, v):
        if not v.startswith('http://') and not v.startswith('https://'):
            raise ValueError('QWEATHER_BASE_URL 必须以 http:// 或 https:// 开头')
        return v

    model_config = ConfigDict(
        # .env 文件作为可选配置源，优先从环境变量读取
        env_file=Path(__file__).parent / '.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        env_ignore_empty=True,
        # 允许从进程环境变量中读取配置
        extra='ignore'
    )


config = Settings()

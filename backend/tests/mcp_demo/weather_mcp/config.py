from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict


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
        env_file=".env",
        case_sensitive=True,
        env_ignore_empty=True
    )


config = Settings()

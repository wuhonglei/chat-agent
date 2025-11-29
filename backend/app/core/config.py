"""Application configuration"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.models.config import (
    AppConfig,
    CloudbaseConfig,
    DatabaseConfig,
    LLMConfig,
    MCPConfig,
    SecurityConfig,
    StorageConfig,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """从 YAML 文件加载配置的自定义设置源"""

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str | None]:
        """获取字段值（从 YAML 文件中）"""
        config_file = Path('config.yaml')
        if not config_file.exists():
            return None, None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f) or {}

            # 递归查找字段值
            keys = field_name.split('__')
            value = yaml_data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None, None

            return value, None
        except Exception:
            return None, None

    def __call__(self) -> dict[str, Any]:
        """加载并返回配置字典"""
        config_file = Path('config.yaml')
        if not config_file.exists():
            # 如果 YAML 文件不存在，返回空字典，让其他源处理
            return {}

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f) or {}
            return yaml_data
        except Exception as e:
            # 如果 YAML 文件解析失败，记录错误但不中断程序
            import sys
            print(f"Warning: Failed to load config.yaml: {e}", file=sys.stderr)
            return {}


class Settings(BaseSettings):
    """Application settings - 使用层级结构匹配 YAML 配置"""

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(..., description="LLM 模型配置")
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cloudbase: CloudbaseConfig = Field(..., description="Cloudbase 配置")
    database: DatabaseConfig = Field(..., description="数据库配置")

    model_config = SettingsConfigDict(
        extra='allow',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        自定义配置源优先级
        优先级（从高到低）：
        1. 初始化参数（init_settings）
        2. YAML 配置文件（config.yaml）
        """
        yaml_settings = YamlConfigSettingsSource(settings_cls)
        return (
            init_settings,      # 初始化参数（最高优先级）
            yaml_settings,      # YAML 配置文件
        )


settings = Settings()

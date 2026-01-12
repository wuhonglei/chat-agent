"""Nacos 配置相关"""

from typing import Any
import json
import yaml
from nacos import NacosClient
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from app.utils.logger import logger


class NacosConnectionConfig(BaseSettings):
    """Nacos 连接配置 - 从环境变量读取"""

    server_addresses: str = Field(
        ..., description="Nacos 服务地址"
    )
    namespace: str = Field('public', description="Nacos 命名空间ID")
    username: str = Field(..., description="Nacos 登录用户名")
    password: str = Field(..., description="Nacos 登录密码")
    data_id: str = Field(..., description="配置ID")
    group: str = Field(default="DEFAULT_GROUP", description="配置分组")
    config_type: str = Field(default="yaml", description="配置格式")

    model_config = SettingsConfigDict(
        env_prefix="NACOS_",
        env_file=".env",
        case_sensitive=False,
        extra='ignore',
    )


class NacosConfigSettingsSource(PydanticBaseSettingsSource):
    """从 Nacos 配置中心加载 YAML 配置的自定义设置源"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._config_cache: dict[str, Any] | None = None

    def _get_nacos_config(self) -> dict[str, Any]:
        """从 Nacos 获取配置"""
        # 如果已经缓存，直接返回
        if self._config_cache is not None:
            return self._config_cache

        # 使用 pydantic_settings 从环境变量读取 Nacos 配置信息
        nacos_conn_config = NacosConnectionConfig()

        try:
            # 初始化 Nacos 客户端
            client_kwargs = {
                "server_addresses": nacos_conn_config.server_addresses,
            }
            if nacos_conn_config.namespace:
                client_kwargs["namespace"] = nacos_conn_config.namespace
            if nacos_conn_config.username and nacos_conn_config.password:
                client_kwargs["username"] = nacos_conn_config.username
                client_kwargs["password"] = nacos_conn_config.password

            client = NacosClient(**client_kwargs)

            # 获取配置内容
            config_content = client.get_config(
                data_id=nacos_conn_config.data_id,
                group=nacos_conn_config.group,
                timeout=5,
            )

            if not config_content:
                raise ValueError(
                    f"Failed to get config from Nacos: "
                    f"data_id={nacos_conn_config.data_id}, "
                    f"group={nacos_conn_config.group}"
                )

            # 根据配置类型解析
            if nacos_conn_config.config_type == "yaml":
                parsed_config = yaml.safe_load(config_content) or {}
            elif nacos_conn_config.config_type == "json":
                parsed_config = json.loads(config_content)
            else:
                logger.warning(
                    f"Warning: Unsupported config type: "
                    f"{nacos_conn_config.config_type}"
                )
                parsed_config = {}

            self._config_cache = parsed_config
            return parsed_config

        except Exception as e:
            # 如果 Nacos 配置获取失败，记录错误但不中断程序

            logger.error(
                "Failed to load config from Nacos",
                error=e,
            )
            self._config_cache = {}
            return {}

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str | None]:
        """获取字段值（从 Nacos 配置中）"""
        yaml_data = self._get_nacos_config()
        if not yaml_data:
            return None, None

        try:
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
        return self._get_nacos_config()

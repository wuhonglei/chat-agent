"""Nacos 配置相关"""

import json
import os
from pathlib import Path
from typing import Any

import yaml
from nacos import NacosClient
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.utils.logger import logger


class NacosConnectionConfig(BaseSettings):
    """Nacos 连接配置 - 从环境变量读取"""

    server_addresses: str = Field(..., description="Nacos 服务地址")
    namespace: str = Field("public", description="Nacos 命名空间ID")
    username: str = Field(..., description="Nacos 登录用户名")
    password: str = Field(..., description="Nacos 登录密码")
    data_id: str = Field(..., description="配置ID")
    group: str = Field(default="DEFAULT_GROUP", description="配置分组")
    config_type: str = Field(default="yaml", description="配置格式")

    model_config = SettingsConfigDict(
        env_prefix="NACOS_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


class NacosConfigSettingsSource(PydanticBaseSettingsSource):
    """从 Nacos 配置中心加载 YAML 配置的自定义设置源"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._config_cache: dict[str, Any] | None = None
        self._nacos_client: NacosClient | None = None
        self._connection_config: NacosConnectionConfig | None = None
        self._watcher_started: bool = False

    def _config_change_listener(self, config_content: str | dict[str, Any]) -> None:
        """配置变化回调函数

        当 Nacos 配置发生变化时，此函数会被自动调用来更新缓存
        """
        if not config_content:
            logger.warning("收到空的配置内容，跳过更新")
            return

        try:
            # 处理不同格式的配置内容
            actual_content = None
            if isinstance(config_content, dict):
                # 如果是字典格式，提取实际的配置内容
                actual_content = config_content.get("content") or config_content.get(
                    "raw_content"
                )
            else:
                # 字符串格式：直接使用
                actual_content = config_content

            if not actual_content:
                logger.warning("未找到有效的配置内容")
                return

            # 根据配置类型解析新的配置内容
            if (
                self._connection_config
                and self._connection_config.config_type == "yaml"
            ):
                new_config = yaml.safe_load(actual_content) or {}
            elif (
                self._connection_config
                and self._connection_config.config_type == "json"
            ):
                new_config = json.loads(actual_content)
            else:
                logger.warning(
                    f"不支持的配置类型: {self._connection_config.config_type if self._connection_config else 'unknown'}"
                )
                return

            # 更新缓存
            old_config_keys = (
                set(self._config_cache.keys()) if self._config_cache else set()
            )
            self._config_cache = new_config
            new_config_keys = set(new_config.keys())

            # 计算配置变化
            added_keys = new_config_keys - old_config_keys
            removed_keys = old_config_keys - new_config_keys

            logger.info(
                "Nacos 配置已更新",
                data_id=self._connection_config.data_id
                if self._connection_config
                else "unknown",
                group=self._connection_config.group
                if self._connection_config
                else "unknown",
                config_keys_count=len(new_config),
                added_keys=list(added_keys) if added_keys else None,
                removed_keys=list(removed_keys) if removed_keys else None,
                config_size=len(actual_content)
                if isinstance(actual_content, str)
                else "unknown",
            )

        except Exception as e:
            logger.error(
                "处理配置更新时发生错误",
                error=e,
                config_type=type(config_content).__name__,
                has_content=bool(config_content),
            )

    def _ensure_nacos_client(self) -> None:
        """确保 Nacos 客户端已初始化并启动监听器"""
        if self._nacos_client is not None:
            return

        # 初始化连接配置（从环境变量 NACOS_* 加载）
        if self._connection_config is None:
            self._connection_config = NacosConnectionConfig()  # type: ignore[call-arg]

        try:
            # 初始化 Nacos 客户端
            client_kwargs = {
                "server_addresses": self._connection_config.server_addresses,
            }
            if self._connection_config.namespace:
                client_kwargs["namespace"] = self._connection_config.namespace
            if self._connection_config.username and self._connection_config.password:
                client_kwargs["username"] = self._connection_config.username
                client_kwargs["password"] = self._connection_config.password

            self._nacos_client = NacosClient(**client_kwargs)

            # 启动配置监听器（只启动一次）
            if not self._watcher_started:
                self._nacos_client.add_config_watcher(
                    data_id=self._connection_config.data_id,
                    group=self._connection_config.group,
                    cb=self._config_change_listener,
                )
                self._watcher_started = True
                logger.info(
                    "Nacos 配置监听器已启动",
                    data_id=self._connection_config.data_id,
                    group=self._connection_config.group,
                )

        except Exception as e:
            logger.error(
                "Failed to initialize Nacos client",
                error=e,
            )
            raise

    def _get_snapshot_path(self) -> Path | None:
        """根据连接配置构造本地快照文件路径。若无法获取连接配置则返回 None。"""
        try:
            if self._connection_config is None:
                self._connection_config = NacosConnectionConfig()  # type: ignore[call-arg]
        except Exception:
            return None
        base = os.environ.get("NACOS_SNAPSHOT_DIR", "nacos-data/snapshot")
        namespace = self._connection_config.namespace or "public"
        name = f"{self._connection_config.data_id}+{self._connection_config.group}+{namespace}"
        return Path(base) / name

    def _load_config_from_snapshot(self) -> dict[str, Any]:
        """从本地快照文件加载配置。Nacos 客户端不可用时使用。"""
        path = self._get_snapshot_path()
        if path is None or not path.is_file():
            return {}
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("无法读取 Nacos 快照文件", path=str(path), error=e)
            return {}
        try:
            if self._connection_config is None:
                # 无法确定类型时按 yaml 尝试
                config = yaml.safe_load(raw) or {}
            elif self._connection_config.config_type == "yaml":
                config = yaml.safe_load(raw) or {}
            elif self._connection_config.config_type == "json":
                config = json.loads(raw)
            else:
                config = yaml.safe_load(raw) or {}
            if config:
                logger.info(
                    "已从本地快照加载 Nacos 配置",
                    path=str(path),
                    config_keys_count=len(config),
                )
            return config
        except Exception as e:
            logger.warning("解析 Nacos 快照文件失败", path=str(path), error=e)
            return {}

    def _get_nacos_config(self) -> dict[str, Any]:
        """从 Nacos 获取配置；失败时尝试使用本地快照。"""
        # 如果已经缓存且客户端已初始化，直接返回缓存
        if self._config_cache is not None and self._nacos_client is not None:
            return self._config_cache

        try:
            # 确保客户端已初始化
            self._ensure_nacos_client()
            assert self._nacos_client is not None
            assert self._connection_config is not None

            # 获取配置内容
            config_content = self._nacos_client.get_config(
                data_id=self._connection_config.data_id,
                group=self._connection_config.group,
                timeout=5,
            )

            if not config_content:
                raise ValueError(
                    f"Failed to get config from Nacos: "
                    f"data_id={self._connection_config.data_id}, "
                    f"group={self._connection_config.group}"
                )

            # 根据配置类型解析
            if self._connection_config.config_type == "yaml":
                parsed_config = yaml.safe_load(config_content) or {}
            elif self._connection_config.config_type == "json":
                parsed_config = json.loads(config_content)
            else:
                logger.warning(
                    f"Warning: Unsupported config type: {self._connection_config.config_type}"
                )
                parsed_config = {}

            self._config_cache = parsed_config
            return parsed_config

        except Exception as e:
            logger.error(
                "Failed to load config from Nacos",
                error=e,
            )
            # Nacos 失败时尝试使用本地快照
            snapshot_config = self._load_config_from_snapshot()
            if snapshot_config:
                self._config_cache = snapshot_config
                return snapshot_config
            self._config_cache = {}
            return {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """获取字段值（从 Nacos 配置中）

        返回 (value, key, value_is_complex)，与 PydanticBaseSettingsSource 约定一致。
        当无值时返回 (None, '', False)。
        """
        yaml_data = self._get_nacos_config()
        if not yaml_data:
            return None, "", False

        try:
            # 递归查找字段值
            keys = field_name.split("__")
            value = yaml_data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None, "", False

            return value, field_name, False
        except Exception:
            return None, "", False

    def __call__(self) -> dict[str, Any]:
        """加载并返回配置字典"""
        return self._get_nacos_config()

    def close(self) -> None:
        """关闭 Nacos 客户端连接"""
        if self._nacos_client:
            try:
                self._nacos_client.close()
                logger.info("Nacos 客户端连接已关闭")
            except Exception as e:
                logger.error("关闭 Nacos 客户端连接时发生错误", error=e)
            finally:
                self._nacos_client = None
                self._watcher_started = False

    def __del__(self) -> None:
        """析构函数，确保资源被正确清理"""
        self.close()

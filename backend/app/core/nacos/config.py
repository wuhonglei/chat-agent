"""Nacos 配置相关（nacos-sdk-python v3 / v2.nacos 异步客户端）"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from v2.nacos import (
    ClientConfig,
    ClientConfigBuilder,
    ConfigParam,
    GRPCConfig,
    NacosConfigService,
)

from app.utils.logger import logger

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _resolve_under_backend(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (_BACKEND_ROOT / p).resolve()


def _nacos_source_skipped() -> bool:
    v = os.environ.get("NACOS_SKIP_LOAD", "").strip().lower()
    return v in ("1", "true", "yes")


def _nacos_grpc_config() -> GRPCConfig:
    timeout_ms = 5000
    if v := os.environ.get("NACOS_GRPC_TIMEOUT_MS", "").strip():
        timeout_ms = int(v, 10)
    port_offset = 1000
    if v := os.environ.get("NACOS_GRPC_PORT_OFFSET", "").strip():
        port_offset = int(v, 10)
    return GRPCConfig(grpc_timeout=timeout_ms, port_offset=port_offset)


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


class _NacosAsyncBridge:
    _instance: _NacosAsyncBridge | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    @classmethod
    def get(cls) -> _NacosAsyncBridge:
        with cls._lock:
            if cls._instance is None:
                inst = cls()
                inst._start_thread()
                cls._instance = inst
            return cls._instance

    def _start_thread(self) -> None:
        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            loop.run_forever()

        self._thread = threading.Thread(
            target=runner,
            name="nacos-sdk-v3-async",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError("Nacos 异步桥接线程启动超时")

    def run(self, coro: Coroutine[Any, Any, Any], timeout: float = 60) -> Any:
        if self._loop is None:
            raise RuntimeError("Nacos event loop 未初始化")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


class NacosConfigSettingsSource(PydanticBaseSettingsSource):
    """从 Nacos 配置中心加载 YAML/JSON 配置"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._config_cache: dict[str, Any] | None = None
        self._nacos_client: NacosConfigService | None = None
        self._connection_config: NacosConnectionConfig | None = None
        self._config_listener: Any | None = None
        self._cache_lock = threading.Lock()
        self._client_init_lock = threading.Lock()

    def _resolve_connection_config(
        self, *, optional: bool
    ) -> NacosConnectionConfig | None:
        if self._connection_config is not None:
            return self._connection_config
        try:
            self._connection_config = NacosConnectionConfig()  # type: ignore[call-arg]
            return self._connection_config
        except Exception:
            if optional:
                return None
            raise

    def _namespace_id_for_sdk(self) -> str:
        assert self._connection_config is not None
        ns = (self._connection_config.namespace or "").strip()
        if ns.lower() == "public":
            return ""
        return ns

    def _build_client_config(self) -> ClientConfig:
        assert self._connection_config is not None
        cc = self._connection_config
        cache_dir = _resolve_under_backend(
            os.environ.get("NACOS_CACHE_DIR", "nacos-data")
        )
        return (
            ClientConfigBuilder()
            .server_address(cc.server_addresses)
            .namespace_id(self._namespace_id_for_sdk())
            .username(cc.username)
            .password(cc.password)
            .cache_dir(str(cache_dir))
            .grpc_config(_nacos_grpc_config())
            .log_level("INFO")
            .build()
        )

    def _parse_config_content(self, raw: str) -> dict[str, Any]:
        assert self._connection_config is not None
        if not raw or not raw.strip():
            return {}
        ct = self._connection_config.config_type
        if ct == "yaml":
            loaded = yaml.safe_load(raw)
            return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
        if ct == "json":
            loaded = json.loads(raw)
            return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
        logger.warning("不支持的配置类型", config_type=ct)
        return {}

    def _apply_parsed_config(
        self,
        new_config: dict[str, Any],
        *,
        actual_content: str | None = None,
    ) -> None:
        with self._cache_lock:
            old_keys = set(self._config_cache.keys()) if self._config_cache else set()
            self._config_cache = new_config
            new_keys = set(new_config.keys())
        assert self._connection_config is not None
        added = new_keys - old_keys
        removed = old_keys - new_keys
        logger.info(
            "Nacos 配置已更新",
            data_id=self._connection_config.data_id,
            group=self._connection_config.group,
            config_keys_count=len(new_config),
            added_keys=list(added) if added else None,
            removed_keys=list(removed) if removed else None,
            config_size=len(actual_content)
            if isinstance(actual_content, str)
            else "unknown",
        )

    def _make_config_listener(self) -> Any:
        async def config_listener(
            tenant: str,
            group: str,
            data_id: str,
            content: str,
        ) -> None:
            try:
                if not content:
                    logger.warning("收到空的配置内容，跳过更新")
                    return
                new_config = self._parse_config_content(content)
                self._apply_parsed_config(new_config, actual_content=content)
            except Exception as e:
                logger.error(
                    "处理配置更新时发生错误",
                    error=e,
                    tenant=tenant,
                    group=group,
                    data_id=data_id,
                )

        return config_listener

    def _ensure_nacos_client(self) -> None:
        with self._client_init_lock:
            if self._nacos_client is not None:
                return
            self._resolve_connection_config(optional=False)
            bridge = _NacosAsyncBridge.get()
            conn = self._connection_config
            assert conn is not None
            listener = self._make_config_listener()
            self._config_listener = listener

            async def setup() -> NacosConfigService:
                client = await NacosConfigService.create_config_service(
                    self._build_client_config()
                )
                try:
                    await client.add_listener(conn.data_id, conn.group, listener)
                    logger.info(
                        "Nacos 配置监听器已启动 (v3)",
                        data_id=conn.data_id,
                        group=conn.group,
                    )
                except Exception as le:
                    logger.warning(
                        "Nacos add_listener 失败，将仅使用拉取配置（无热更新）",
                        error=le,
                        exc_info=True,
                    )
                return client

            try:
                self._nacos_client = bridge.run(setup(), timeout=90)
            except Exception as e:
                logger.error(
                    "Failed to initialize Nacos client",
                    error=e,
                    server_addresses=conn.server_addresses,
                    data_id=conn.data_id,
                    group=conn.group,
                    exc_info=True,
                )
                self._config_listener = None
                raise

    def _iter_snapshot_paths(self) -> list[Path]:
        if self._resolve_connection_config(optional=True) is None:
            return []
        conn = self._connection_config
        assert conn is not None
        cache_root = _resolve_under_backend(
            os.environ.get("NACOS_CACHE_DIR", "nacos-data")
        )
        snap_root = _resolve_under_backend(
            os.environ.get("NACOS_SNAPSHOT_DIR", "nacos-data/snapshot")
        )
        data_id, group = conn.data_id, conn.group
        raw_ns = (conn.namespace or "").strip() or "public"
        tenants = list(
            dict.fromkeys(
                (self._namespace_id_for_sdk(), raw_ns, "public", ""),
            )
        )
        paths: list[Path] = []
        for tenant in tenants:
            paths.append(cache_root / "config" / f"{data_id}@@{group}@@{tenant}")
        for ns in dict.fromkeys((raw_ns, "public", "")):
            paths.append(snap_root / f"{data_id}+{group}+{ns}")
        return paths

    def _load_config_from_snapshot(self) -> dict[str, Any]:
        candidates = self._iter_snapshot_paths()
        existing = [p for p in candidates if p.is_file()]
        if not existing:
            logger.warning(
                "未找到本地 Nacos 快照/v3 缓存文件",
                backend_root=str(_BACKEND_ROOT),
                tried=[str(p) for p in candidates],
            )
            return {}
        path = existing[0]
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("无法读取 Nacos 快照文件", path=str(path), error=e)
            return {}
        try:
            config = self._parse_config_content(raw)
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
        if _nacos_source_skipped():
            return {}

        with self._cache_lock:
            if self._config_cache is not None and self._nacos_client is not None:
                return dict(self._config_cache)

        try:
            self._ensure_nacos_client()
            assert self._nacos_client is not None
            conn = self._connection_config
            assert conn is not None
            bridge = _NacosAsyncBridge.get()
            client = self._nacos_client

            async def fetch() -> str:
                content = await client.get_config(
                    ConfigParam(data_id=conn.data_id, group=conn.group)
                )
                return str(content) if content is not None else ""

            config_content = bridge.run(fetch(), timeout=30)
            if not config_content:
                raise ValueError(
                    f"Failed to get config from Nacos: "
                    f"data_id={conn.data_id}, group={conn.group}"
                )
            parsed = self._parse_config_content(config_content)
            with self._cache_lock:
                self._config_cache = parsed
            return parsed

        except Exception as e:
            snapshot_config = self._load_config_from_snapshot()
            if snapshot_config:
                with self._cache_lock:
                    self._config_cache = snapshot_config
                return snapshot_config
            logger.exception(
                "Nacos 配置拉取失败且未找到本地快照/v3 缓存（完整堆栈见上）",
            )
            c = self._resolve_connection_config(optional=True)
            conn_hint = (
                f"data_id={c.data_id} group={c.group} "
                f"server_addresses={c.server_addresses}"
                if c
                else "无法读取 NACOS_* 连接信息（请检查 .env）"
            )
            raise RuntimeError(
                "无法加载应用配置：连接 Nacos 失败，且本地无可用快照或 v3 缓存文件。\n"
                "说明：nacos-sdk-python v3 依赖 Nacos 3.x（gRPC）；若服务端为 2.x 将无法连接。\n"
                "可选处理：\n"
                "  1) 修复网络/认证并确保 Nacos 3.x 可访问；\n"
                f"  2) 将配置 YAML 放到 backend 目录下（根路径：{_BACKEND_ROOT}），例如：\n"
                "       nacos-data/snapshot/{DATA_ID}+{GROUP}+{NAMESPACE}\n"
                "       或 nacos-data/config/{DATA_ID}@@{GROUP}@@{tenant}\n"
                "  3) 在 .env 中用嵌套键补全所有必填项；\n"
                "  4) 若完全不用 Nacos，设置 NACOS_SKIP_LOAD=1（需 .env 已包含全部必填配置）。\n"
                f"当前：{conn_hint}"
            ) from e

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        yaml_data = self._get_nacos_config()
        if not yaml_data:
            return None, "", False
        keys = field_name.split("__")
        value: Any = yaml_data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None, "", False
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._get_nacos_config()

    def close(self) -> None:
        if not self._nacos_client:
            return
        client = self._nacos_client
        listener = self._config_listener
        conn = self._connection_config
        self._nacos_client = None
        self._config_listener = None

        async def shutdown() -> None:
            if conn is not None and listener is not None:
                try:
                    await client.remove_listener(conn.data_id, conn.group, listener)
                except Exception as e:
                    logger.warning("移除 Nacos 监听器时出错", error=e)
            try:
                await client.shutdown()
            except Exception as e:
                logger.error("关闭 Nacos 客户端时出错", error=e)

        try:
            _NacosAsyncBridge.get().run(shutdown(), timeout=30)
            logger.info("Nacos 客户端连接已关闭")
        except Exception as e:
            logger.error("关闭 Nacos 客户端连接时发生错误", error=e)

    def __del__(self) -> None:
        self.close()

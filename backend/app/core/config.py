"""Application configuration"""

import threading
from typing import Any, cast

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.core.nacos.config import NacosConfigSettingsSource
from app.schemas.config import (
    AppConfig,
    ChatContextConfig,
    CORSConfig,
    DatabaseConfig,
    EmbeddingModelConfig,
    KbFileRagConfig,
    LangfuseConfig,
    MCPConfig,
    ModelsConfig,
    PdfMarkdownConfig,
    SandboxConfig,
    SecurityConfig,
    SmsConfig,
    StorageConfig,
    WechatConfig,
)
from app.utils.logger import logger


class Settings(BaseSettings):
    """Application settings - 使用层级结构匹配 YAML 配置"""

    app: AppConfig = Field(default_factory=AppConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    models: ModelsConfig = Field(
        description="模型配置（providers + scenarios 两层结构）"
    )
    embedding_model: EmbeddingModelConfig = Field(description="Embedding 模型 API 配置")
    mcp: MCPConfig = Field(description="MCP 工具配置")
    storage: StorageConfig = Field(
        default_factory=StorageConfig,
        description="存储配置（头像本地目录）",
    )
    security: SecurityConfig = Field(description="JWT 安全配置")
    sms: SmsConfig = Field(description="腾讯云短信配置")
    database: DatabaseConfig = Field(description="PostgreSQL 数据库配置")
    pdf_markdown: PdfMarkdownConfig = Field(
        default_factory=PdfMarkdownConfig,
        description="PDF 转 Markdown 配置",
    )
    chat_context: ChatContextConfig = Field(
        default_factory=ChatContextConfig, description="对话上下文配置"
    )
    kb_file_rag: KbFileRagConfig = Field(
        default_factory=KbFileRagConfig,
        description="知识库上传文件分块与 RAG 相关配置",
    )
    sandbox: SandboxConfig = Field(
        default_factory=SandboxConfig,
        description="Shell 沙箱执行配置",
    )
    wechat: WechatConfig = Field(description="微信配置")
    langfuse: LangfuseConfig = Field(
        default_factory=LangfuseConfig,
        description="Langfuse 可观测配置",
    )

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_nested_delimiter="__",  # 支持使用 __ 访问嵌套字段，如 DATABASE__HOST
    )

    @model_validator(mode="after")
    def validate_models(self) -> "Settings":
        models = self.models
        required_scenarios = ("text_generation", "title_generation", "summarization")
        for scenario_name in required_scenarios:
            if scenario_name not in models.scenarios:
                raise ValueError(f"models.scenarios 必须包含 '{scenario_name}'")

        for scenario_name, scenario in models.scenarios.items():
            refs = [scenario.default_model, *scenario.alternatives]
            for ref in refs:
                provider_name, _, model_key = ref.partition("/")
                if not provider_name or not model_key:
                    raise ValueError(
                        f"models.scenarios.{scenario_name} 模型引用非法: {ref!r}，"
                        "应为 'provider/model_name'"
                    )
                provider = models.providers.get(provider_name)
                if provider is None:
                    raise ValueError(
                        f"models.scenarios.{scenario_name} 引用了不存在的 provider: "
                        f"{provider_name!r}（ref={ref!r}）"
                    )
                if model_key not in provider.models:
                    raise ValueError(
                        f"models.scenarios.{scenario_name} 引用了 provider "
                        f"{provider_name!r} 下不存在的模型: {model_key!r}（ref={ref!r}）"
                    )
        return self

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
        1. 初始化参数（init_settings）- Settings 类构造函数初始化参数
        2. 环境变量（env_settings）- 可覆盖 Nacos 配置，用于 Docker 等场景
        3. .env 文件（dotenv_settings）- 本地开发覆盖 Nacos 配置，如 DATABASE__HOST
        4. Nacos 配置中心（从 .env 文件读取连接信息）
        """
        nacos_settings = NacosConfigSettingsSource(settings_cls)
        return (
            init_settings,  # 初始化参数（最高优先级）
            env_settings,  # 环境变量（可覆盖 Nacos 配置）
            dotenv_settings,  # .env 文件（本地覆盖，如 DATABASE__HOST）
            nacos_settings,  # Nacos 配置中心
        )


def _build_settings() -> Settings:
    # Settings() 从 model_config 配置的 env/nacos 等源加载，无参调用在运行时可工作，mypy 无法推断
    return Settings()  # type: ignore[call-arg]


_settings_reload_lock = threading.Lock()
_current_settings: Settings = _build_settings()


class _SettingsProxy:
    """转发到当前 Settings 实例，保证 Nacos 热更新后导入配置始终读取最新值。"""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return getattr(_current_settings, name)


def reload_settings() -> None:
    """用环境变量 / .env / Nacos 当前缓存重新构造 Settings 并切换全局引用（由 Nacos 监听器或测试调用）。"""
    global _current_settings
    with _settings_reload_lock:
        _current_settings = _build_settings()
    logger.info("Settings 已重新加载（Nacos 或手动 reload_settings）")
    try:
        from app.mcp.reload import on_settings_reloaded

        on_settings_reloaded()
    except Exception as e:
        logger.error(
            "Settings 重载后调度 MCP 热更新失败",
            error=e,
            exc_info=True,
        )


settings = cast(Settings, _SettingsProxy())

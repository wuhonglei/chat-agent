"""Application configuration"""

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.core.nacos.config import NacosConfigSettingsSource
from app.schemas.config import (
    AppConfig,
    ChatContextConfig,
    DatabaseConfig,
    EmbeddingModelConfig,
    LLMConfig,
    MCPConfig,
    SecurityConfig,
    SmsConfig,
    StorageConfig,
    SummarizerModelConfig,
    WechatConfig,
)


class Settings(BaseSettings):
    """Application settings - 使用层级结构匹配 YAML 配置"""

    app: AppConfig = Field(default_factory=AppConfig)
    response_model: LLMConfig = Field(description="响应生成模型 API 配置")
    tool_call_model: LLMConfig = Field(description="mcp 工具调用模型 API 配置")
    summarizer_model: SummarizerModelConfig = Field(description="摘要生成模型 API 配置")
    embedding_model: EmbeddingModelConfig = Field(description="Embedding 模型 API 配置")
    mcp: MCPConfig = Field(description="MCP 工具配置")
    storage: StorageConfig = Field(description="S3 存储配置")
    security: SecurityConfig = Field(description="JWT 安全配置")
    sms: SmsConfig = Field(description="腾讯云短信配置")
    database: DatabaseConfig = Field(description="PostgreSQL 数据库配置")
    chat_context: ChatContextConfig = Field(
        default_factory=ChatContextConfig, description="对话上下文配置"
    )
    wechat: WechatConfig = Field(description="微信配置")
    component_schema_api_url: str = Field(description="组件 Schema API URL")

    model_config = SettingsConfigDict(
        extra="allow",
        env_nested_delimiter="__",  # 支持使用 __ 访问嵌套字段，如 DATABASE__HOST
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
        1. 初始化参数（init_settings）- Settings 类构造函数初始化参数
        2. 环境变量（env_settings）- 可覆盖 Nacos 配置，用于 Docker 等场景
        3. Nacos 配置中心（从 .env 文件读取连接信息）
        """
        nacos_settings = NacosConfigSettingsSource(settings_cls)
        return (
            init_settings,  # 初始化参数（最高优先级）
            env_settings,  # 环境变量（可覆盖 Nacos 配置）
            nacos_settings,  # Nacos 配置中心
        )


# Settings() 从 model_config 配置的 env/nacos 等源加载，无参调用在运行时可工作，mypy 无法推断
settings = Settings()  # type: ignore[call-arg]

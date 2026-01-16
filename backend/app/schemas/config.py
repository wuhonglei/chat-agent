"""配置模型定义"""

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用程序基础配置"""

    name: str = "AI Assistant"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000


class BaseLLMModelConfig(BaseModel):
    """LLM 模型 API 基础配置"""

    api_key: str = Field(description="API 密钥")
    api_base: str = Field(description="API 基础地址")
    model_name: str = Field(description="默认模型名称")


class EmbeddingModelConfig(BaseLLMModelConfig):
    """Embedding 模型 API 配置"""

    pass


class SummarizerModelConfig(BaseLLMModelConfig):
    """摘要生成模型 API 配置"""

    pass


class LLMConfig(BaseModel):
    """LLM 模型 API 配置"""

    api_key: str = Field(description="LLM API 密钥")
    api_base: str = Field(description="LLM API 基础地址")
    model_name: str = Field(description="默认模型名称")
    think_model_name: str = Field(description="推理模型名称")


class Context7Config(BaseModel):
    """Context7 MCP 配置"""

    api_key: str = Field(description="Context7 API 密钥")


class ConfluenceMCPConfig(BaseModel):
    """Confluence MCP 配置"""

    CONFLUENCE_URL: str = Field(description="Confluence URL")  # 与环境变量名一致
    CONFLUENCE_PERSONAL_TOKEN: str = Field(
        description="Confluence Personal Token"
    )  # 与环境变量名一致
    # 认证类型：pat, basic, oauth，与环境变量名一致
    CONFLUENCE_AUTH_TYPE: str = Field(
        description="Confluence 认证类型：pat, basic, oauth"
    )


class WeatherMCPConfig(BaseModel):
    """Weather MCP 配置"""

    QWEATHER_API_KEY: str = Field(description="和风天气 API 密钥")  # 与环境变量名一致
    QWEATHER_BASE_URL: str = Field(
        description="和风天气 API 基础地址"
    )  # 与环境变量名一致
    QWEATHER_TIMEOUT: int = Field(
        description="和风天气 API 超时时间"
    )  # 与环境变量名一致


class TavilyMCPConfig(BaseModel):
    """Tavily MCP 配置"""

    TAVILY_API_KEY: str = Field(description="Tavily API 密钥")  # 与环境变量名一致


class MCPConfig(BaseModel):
    """MCP 配置"""

    context7: Context7Config = Field(default_factory=Context7Config)
    confluence_mcp: ConfluenceMCPConfig = Field(
        default_factory=ConfluenceMCPConfig,
    )
    weather_mcp: WeatherMCPConfig = Field(
        default_factory=WeatherMCPConfig,
    )
    tavily_mcp: TavilyMCPConfig = Field(
        default_factory=TavilyMCPConfig,
    )


class TencentCOSConfig(BaseModel):
    """腾讯云 COS 存储配置"""

    secret_id: str = Field(..., description="The secret ID of the storage")
    secret_key: str = Field(..., description="The secret key of the storage")
    region: str = Field("ap-guangzhou", description="The region of the storage")
    bucket: str = Field("ai-chat-1258352625", description="The bucket of the storage")


class StorageConfig(BaseModel):
    """存储配置"""

    avatar_dir: str = "./data/avatars"
    tencent_cos: TencentCOSConfig = Field(default_factory=TencentCOSConfig)


class JWTConfig(BaseModel):
    """JWT 安全配置"""

    version: str = Field(description="JWT 版本")
    algorithm: str = Field(description="JWT 算法")
    private_key: str = Field(description="私钥内容（PEM 格式）")
    public_key: str = Field(description="公钥内容（PEM 格式）")


class SecurityConfig(BaseModel):
    """安全配置"""

    jwt: JWTConfig = Field(default_factory=JWTConfig)


class CloudbaseConfig(BaseModel):
    """Cloudbase 配置"""

    env_id: str = Field(..., description="The environment ID of the Cloudbase")


class DatabaseConfig(BaseModel):
    """PostgreSQL 数据库配置"""

    host: str = Field(description="PostgreSQL 数据库主机")
    port: int = Field(description="PostgreSQL 数据库端口")
    db: str = Field(description="PostgreSQL 数据库名称")
    username: str = Field(description="PostgreSQL 数据库用户名")
    password: str = Field(description="PostgreSQL 数据库密码")


class CompressionConfig(BaseModel):
    """上下文压缩配置"""

    enabled: bool = Field(default=True, description="是否启用上下文压缩")
    relevance_enabled: bool = Field(default=True, description="是否启用相关性过滤")
    reference_enabled: bool = Field(default=True, description="是否启用引用")
    summary_enabled: bool = Field(default=True, description="是否启用摘要")
    tool_result_max_tokens: int = Field(
        default=5000, description="单个工具结果最大token数"
    )
    summary_max_tokens: int = Field(default=1200, description="摘要目标最大token数")
    reference_dir: str = Field(
        default="./data/tool_results", description="引用存储目录"
    )

"""配置模型定义"""

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用程序基础配置"""
    name: str = "AI Assistant"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000


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
        description="Confluence Personal Token")  # 与环境变量名一致
    # 认证类型：pat, basic, oauth，与环境变量名一致
    CONFLUENCE_AUTH_TYPE: str = Field(
        description="Confluence 认证类型：pat, basic, oauth")


class WeatherMCPConfig(BaseModel):
    """Weather MCP 配置"""
    QWEATHER_API_KEY: str = Field(description="和风天气 API 密钥")  # 与环境变量名一致
    QWEATHER_BASE_URL: str = Field(description="和风天气 API 基础地址")  # 与环境变量名一致
    QWEATHER_TIMEOUT: int = Field(description="和风天气 API 超时时间")  # 与环境变量名一致


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
    region: str = Field(
        'ap-guangzhou', description="The region of the storage")
    bucket: str = Field("ai-chat-1258352625",
                        description="The bucket of the storage")


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


class SingleRoundConfig(BaseModel):
    """单轮压缩配置"""
    max_web_content_length: int = Field(description="网页内容最大长度")
    max_search_results: int = Field(description="搜索结果最大数量")
    max_generic_length: int = Field(description="通用内容最大长度")


class IterationCompressionConfig(BaseModel):
    """迭代间压缩配置"""
    max_iteration_context_length: int = Field(description="单次迭代最大上下文长度")
    current_iteration_retention: float = Field(description="当前迭代结果保留率")
    recent_iteration_retention: float = Field(description="最近迭代结果保留率")
    early_iteration_retention: float = Field(description="早期迭代结果保留率")
    compression_trigger_threshold: int = Field(
        description="到目前为止所有工具调用相关消息的累积上下文长度阈值")
    single_result_precompress_threshold: int = Field(description="单结果预压缩阈值")


class MultiRoundConfig(BaseModel):
    """多轮压缩配置（为未来扩展预留）"""
    max_rounds: int = Field(description="最大保留轮次数")
    time_decay_factor: float = Field(description="时间衰减因子")
    relevance_threshold: float = Field(description="相关性阈值")
    max_total_tokens: int = Field(description="总上下文最大token数")


class CompressionConfig(BaseModel):
    """上下文压缩配置"""
    enabled: bool = Field(description="是否启用上下文压缩功能")
    single_round: SingleRoundConfig
    iteration_compression: IterationCompressionConfig
    multi_round: MultiRoundConfig

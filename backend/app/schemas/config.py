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
    api_key: str
    api_base: str = "https://api.deepseek.com/v1"
    model_name: str = "deepseek-chat"
    think_model_name: str = "deepseek-reasoner"


class Context7Config(BaseModel):
    """Context7 MCP 配置"""
    api_key: str = ""


class ConfluenceMCPConfig(BaseModel):
    """Confluence MCP 配置"""
    CONFLUENCE_URL: str = ""  # 与环境变量名一致
    CONFLUENCE_PERSONAL_TOKEN: str = ""  # 与环境变量名一致
    CONFLUENCE_AUTH_TYPE: str = "pat"  # 认证类型：pat, basic, oauth，与环境变量名一致


class WeatherMCPConfig(BaseModel):
    """Weather MCP 配置"""
    QWEATHER_API_KEY: str = ""  # 与环境变量名一致
    QWEATHER_BASE_URL: str = ""  # 与环境变量名一致
    QWEATHER_TIMEOUT: int = 10  # 与环境变量名一致


class TavilyMCPConfig(BaseModel):
    """Tavily MCP 配置"""
    TAVILY_API_KEY: str = ""  # 与环境变量名一致


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
    version: str = "v1"
    algorithm: str = "RS256"
    private_key: str = ""  # 私钥内容（PEM 格式）
    public_key: str = ""  # 公钥内容（PEM 格式）


class SecurityConfig(BaseModel):
    """安全配置"""
    jwt: JWTConfig = Field(default_factory=JWTConfig)


class CloudbaseConfig(BaseModel):
    """Cloudbase 配置"""
    env_id: str = Field(..., description="The environment ID of the Cloudbase")


class DatabaseConfig(BaseModel):
    """PostgreSQL 数据库配置"""
    host: str = "localhost"
    port: int = 5432
    db: str = "ai_assistant_db"
    username: str = Field(...,
                          description="The username of the PostgreSQL database")
    password: str = Field(...,
                          description="The password of the PostgreSQL database")


class SingleRoundConfig(BaseModel):
    """单轮压缩配置"""
    max_web_content_length: int = Field(
        default=8000,
        description="网页内容最大长度"
    )
    max_search_results: int = Field(
        default=10,
        description="搜索结果最大数量"
    )
    max_generic_length: int = Field(
        default=4000,
        description="通用内容最大长度"
    )


class IterationCompressionConfig(BaseModel):
    """迭代间压缩配置"""
    max_iteration_context_length: int = Field(
        default=8000,
        description="单次迭代最大上下文长度"
    )
    current_iteration_retention: float = Field(
        default=0.9,
        description="当前迭代结果保留率"
    )
    recent_iteration_retention: float = Field(
        default=0.6,
        description="最近迭代结果保留率"
    )
    early_iteration_retention: float = Field(
        default=0.3,
        description="早期迭代结果保留率"
    )
    compression_trigger_threshold: int = Field(
        default=10000,
        description="压缩触发阈值"
    )
    single_result_precompress_threshold: int = Field(
        default=3000,
        description="单结果预压缩阈值"
    )


class MultiRoundConfig(BaseModel):
    """多轮压缩配置（为未来扩展预留）"""
    max_rounds: int = Field(
        default=5,
        description="最大保留轮次数"
    )
    time_decay_factor: float = Field(
        default=0.7,
        description="时间衰减因子"
    )
    relevance_threshold: float = Field(
        default=0.6,
        description="相关性阈值"
    )
    max_total_tokens: int = Field(
        default=25000,
        description="总上下文最大token数"
    )


class CompressionConfig(BaseModel):
    """上下文压缩配置"""
    enabled: bool = Field(
        default=True,
        description="是否启用上下文压缩功能"
    )
    single_round: SingleRoundConfig = Field(default_factory=SingleRoundConfig)
    iteration_compression: IterationCompressionConfig = Field(
        default_factory=IterationCompressionConfig)
    multi_round: MultiRoundConfig = Field(default_factory=MultiRoundConfig)

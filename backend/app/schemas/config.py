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

    embedding_dimension: int = Field(default=1024, description="Embedding 维度")


class SummarizerModelConfig(BaseLLMModelConfig):
    """摘要生成模型 API 配置"""

    pass


class LLMConfig(BaseModel):
    """LLM 模型 API 配置"""

    api_key: str = Field(description="LLM API 密钥")
    api_base: str = Field(description="LLM API 基础地址")
    model_name: str = Field(description="默认模型名称")
    think_model_name: str = Field(description="推理模型名称")


class MCPCacheConfig(BaseModel):
    """单个 MCP 的 tools/call 结果缓存配置"""

    cache_enabled: bool = Field(
        default=False,
        description="是否启用缓存",
    )
    cache_dir: str = Field(
        default="./data/mcp_cache",
        description="缓存存储目录（DiskStore）",
    )
    call_tool_ttl: int = Field(
        default=300,
        description="工具调用缓存 TTL（秒）",
    )
    call_tool_excluded: list[str] = Field(
        default_factory=list,
        description="不缓存的工具名列表",
    )


class Context7MCPConfig(BaseModel):
    """Context7 MCP 配置"""

    url: str = Field(description="Context7 URL")
    headers: dict[str, str] = Field(description="Context7 Headers")
    verify_ssl: bool = Field(default=True, description="是否验证 SSL")
    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


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
    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
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
    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


class TavilyMCPConfig(BaseModel):
    """Tavily MCP 配置"""

    TAVILY_API_KEY: str = Field(description="Tavily API 密钥")  # 与环境变量名一致
    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


class IpLocatorMCPConfig(BaseModel):
    """IP Locator MCP 配置"""

    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


class TimeMCPConfig(BaseModel):
    """Time MCP 配置"""

    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


class CodeExecMCPConfig(BaseModel):
    """Code Exec MCP 配置"""

    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )


class MCPConfig(BaseModel):
    """MCP 配置"""

    context7_mcp: Context7MCPConfig = Field(
        default_factory=Context7MCPConfig  # type: ignore[arg-type]
    )
    confluence_mcp: ConfluenceMCPConfig = Field(
        default_factory=ConfluenceMCPConfig  # type: ignore[arg-type]
    )
    weather_mcp: WeatherMCPConfig = Field(
        default_factory=WeatherMCPConfig  # type: ignore[arg-type]
    )
    tavily_mcp: TavilyMCPConfig = Field(
        default_factory=TavilyMCPConfig  # type: ignore[arg-type]
    )
    ip_locator_mcp: IpLocatorMCPConfig = Field(
        default_factory=IpLocatorMCPConfig,
        description="IP Locator MCP 配置",
    )
    time_mcp: TimeMCPConfig = Field(
        default_factory=TimeMCPConfig,
        description="Time MCP 配置",
    )
    code_exec_mcp: CodeExecMCPConfig = Field(
        default_factory=CodeExecMCPConfig,
        description="Code Exec MCP 配置",
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
    tencent_cos: TencentCOSConfig = Field(
        default_factory=TencentCOSConfig  # type: ignore[arg-type]
    )


class JWTConfig(BaseModel):
    """JWT 安全配置"""

    version: str = Field(description="JWT 版本")
    algorithm: str = Field(description="JWT 算法")
    private_key: str = Field(description="私钥内容（PEM 格式）")
    public_key: str = Field(description="公钥内容（PEM 格式）")


class SecurityConfig(BaseModel):
    """安全配置"""

    jwt: JWTConfig = Field(
        default_factory=JWTConfig  # type: ignore[arg-type]
    )


class SmsConfig(BaseModel):
    """短信配置"""

    tencentcloud_secret_id: str = Field(..., description="腾讯云 Secret ID")
    tencentcloud_secret_key: str = Field(..., description="腾讯云 Secret Key")
    region: str = Field(
        "ap-guangzhou", description="腾讯云短信地域 ID，如 ap-guangzhou"
    )
    sms_sdk_app_id: str = Field(..., description="短信 SDK App ID")
    template_id: str = Field(..., description="短信模板 ID")
    sign_name: str = Field(..., description="短信签名")


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
    tool_result_threshold_tokens: int = Field(
        default=5000, description="单个工具结果阈值tokens数"
    )
    tool_result_tolerance_tokens: int = Field(
        default=6000, description="单个工具结果容忍的tokens数"
    )
    tool_result_summary_max_tokens: int = Field(
        default=2000, description="单个工具结果摘要最大tokens数"
    )
    # 历史截断与窗口内工具摘要
    max_history_tokens: int = Field(
        default=32000,
        description="历史消息 token 预算，超出部分从更早消息起截断",
    )
    max_history_rounds: int = Field(
        default=5,
        description="历史最多保留轮数（一轮 = 一条 user + 对应 assistant 及其中 tool）",
    )
    tool_message_summary_threshold_tokens: int = Field(
        default=2000,
        description="单条工具结果超过该 token 数时用 summary/截断参与组装",
    )
    # 窗口外摘要管道
    window_out_summary_enabled: bool = Field(
        default=True,
        description="是否开启窗口外消息摘要管道（截断→摘要→user_context→system 注入）",
    )
    summary_max_tokens: int = Field(
        default=1000,
        description="窗口外摘要最大 token 数，写入与注入时共用",
    )
    # 用户画像语义检索
    user_profile_top_k_facts: int = Field(
        default=5,
        description="用户事实语义检索 top-k",
    )
    user_profile_top_k_preferences: int = Field(
        default=5,
        description="用户偏好语义检索 top-k",
    )
    user_profile_relevance_threshold: float = Field(
        default=0.5,
        description="用户画像相似度阈值，低于此值不注入",
    )
    # 用户画像归纳
    user_profile_extraction_max_tokens: int = Field(
        default=800,
        description="用户事实/偏好归纳 LLM 调用 max_tokens",
    )
    user_profile_prompt_user_content_max_chars: int = Field(
        default=1000,
        description="归纳 prompt 中 user_message_content 最大字符数",
    )
    user_profile_prompt_assistant_content_max_chars: int = Field(
        default=6000,
        description="归纳 prompt 中 assistant_content 最大字符数",
    )
    user_profile_prompt_summary_max_chars: int = Field(
        default=6000,
        description="归纳 prompt 中 summary 最大字符数",
    )
    # Markdown 分块（工具结果相关性过滤）
    markdown_chunk_size: int = Field(
        default=1000,
        description="工具结果 Markdown 分块大小（字符），用于相关性过滤",
    )
    markdown_chunk_overlap: int = Field(
        default=200,
        description="工具结果 Markdown 分块重叠（字符）",
    )


class WechatConfig(BaseModel):
    """微信配置（微信开放平台网站应用）"""

    app_id: str = Field(..., description="微信开放平台 AppID")
    app_secret: str = Field(..., description="微信开放平台 AppSecret")

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

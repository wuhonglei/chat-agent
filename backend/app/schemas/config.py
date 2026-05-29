"""配置模型定义"""

from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用程序基础配置"""

    name: str = "AI Assistant"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000


class CORSConfig(BaseModel):
    """跨域资源共享配置"""

    allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="允许跨域访问的前端源",
    )
    allow_credentials: bool = Field(
        default=True,
        description="是否允许跨域请求携带凭证",
    )
    allow_methods: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许的跨域请求方法",
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许的跨域请求头",
    )


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
    title: str | None = Field(default=None, description="展示标题（可选）")
    description: str | None = Field(default=None, description="说明文案（可选）")
    image_support: bool = Field(
        default=True, description="是否支持图片输入（多模态视觉）"
    )


class MCPServerEntry(BaseModel):
    """单个 MCP Server 的接入配置。

    transport 决定连接方式：
    - fastmcp：进程内通信，需要 module 指定 Python 模块路径
    - http：远程 HTTP 通信，需要 url
    - stdio：子进程通信，需要 command
    """

    enabled: bool = Field(default=True, description="是否启用该 Server")
    transport: Literal["fastmcp", "http", "stdio"] = Field(
        default="fastmcp",
        description="传输方式：fastmcp（进程内）、http（远程）、stdio（子进程）",
    )
    # fastmcp 传输参数
    module: str | None = Field(
        default=None,
        description="Python 模块路径，如 app.mcp.mcp_servers.time_mcp.server（transport=fastmcp 时必填）",
    )
    instance: str = Field(default="mcp", description="模块中 FastMCP 实例的属性名")
    # http 传输参数
    url: str | None = Field(
        default=None, description="远程 MCP Server URL（transport=http 时必填）"
    )
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP 请求头")
    # stdio 传输参数
    command: str | None = Field(
        default=None, description="可执行文件路径（transport=stdio 时必填）"
    )
    args: list[str] = Field(default_factory=list, description="命令行参数")
    env: dict[str, str] = Field(
        default_factory=dict,
        description="业务参数（fastmcp 进程内 Server）或子进程环境变量（stdio）",
    )


class MCPConfig(BaseModel):
    """MCP 配置。

    servers 字段控制加载哪些 MCP Server 及其传输方式。
    留空时使用内置默认值（所有本地 Server + context7 远程 Server）。
    通过设置 enabled: false 可禁用单个 Server，无需删除代码。
    """

    servers: dict[str, MCPServerEntry] = Field(
        default_factory=lambda: {
            "time-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
            ),
            "context7-mcp": MCPServerEntry(
                transport="http",
            ),
            "weather-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.weather_mcp.server",
            ),
            "tavily-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.tavily_mcp.server",
            ),
            "code-exec-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.code_exec_mcp.server",
            ),
            "file-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.file_mcp.server",
            ),
            "shell-mcp": MCPServerEntry(
                module="app.mcp.mcp_servers.shell_mcp.server",
            ),
        },
        description="MCP Server 接入配置（server_name -> MCPServerEntry）",
    )
    normal_mode_servers: list[str] = Field(
        default_factory=lambda: [
            "time-mcp",
            "weather-mcp",
            "tavily-mcp",
            "code-exec-mcp",
            "context7-mcp",
            "zread-mcp",
        ],
        description="普通对话（agent_mode=0）下暴露给 LLM 的 MCP Server 名称列表",
    )
    agent_mode_servers: list[str] = Field(
        default_factory=lambda: [
            "file-mcp",
            "shell-mcp",
            "tavily-mcp",
            "context7-mcp",
            "zread-mcp",
        ],
        description="Agent 模式（agent_mode>0）下暴露给 LLM 的 MCP Server 名称列表",
    )


class StorageConfig(BaseModel):
    """存储配置（头像本地目录）"""

    avatar_dir: str = "./data/avatars"


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


class PdfMarkdownConfig(BaseModel):
    """PDF 转 Markdown 配置"""

    enabled: bool = Field(default=True, description="是否启用 PDF 自动转 Markdown")
    scan_text_threshold: int = Field(
        default=50,
        ge=0,
        description="扫描型判定阈值：前 N 页文字总长度小于该值视为扫描型",
    )
    detect_pages: int = Field(
        default=3,
        ge=1,
        description="PDF 类型检测时读取的页数",
    )
    pp_structure_api_url: str = Field(
        default="https://b5ad76r2h7wfk3g3.aistudio-app.com/layout-parsing",
        description="PP-StructureV3 服务地址",
    )
    pp_structure_token: str = Field(
        default="",
        description="PP-StructureV3 服务 token（从 Nacos 注入）",
    )
    poll_interval_seconds: float = Field(
        default=3.0,
        gt=0,
        description="预留配置：轮询间隔（秒）",
    )
    poll_timeout_seconds: float = Field(
        default=180.0,
        gt=0,
        description="PP-StructureV3 请求超时（秒）",
    )


class KbFileRagConfig(BaseModel):
    """知识库上传文件分块与 RAG 配置"""

    chunk_size: int = Field(
        default=1000,
        ge=1,
        description="上传文件分块大小（字符）",
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="上传文件分块重叠（字符）",
    )
    retrieval_top_k: int = Field(
        default=6,
        ge=1,
        description="会话 RAG 检索 Top-K",
    )
    relevance_score_threshold: float = Field(
        default=0.65,
        ge=0,
        le=1,
        description="会话 RAG 相关性阈值（基于 1-distance）",
    )
    short_doc_max_tokens: int = Field(
        default=10000,
        ge=1,
        description="判定短文档的 token 阈值；短文档可注入全文",
    )
    force_rag_keyword_patterns: list[str] = Field(
        default_factory=lambda: [
            r"根据(文档|附件|材料)",
            r"(附件|文档|材料)里",
            r"(上传|附件).*(总结|归纳|提取|翻译|解释|回答)",
        ],
        description="命中后强制走 RAG（跳过分数门控）",
    )


# ---- 上下文压缩子配置 ----
class ToolResultCompressionConfig(BaseModel):
    """工具结果压缩与摘要配置"""

    enabled: bool = Field(default=True, description="是否启用工具结果压缩与摘要")
    threshold_tokens: int = Field(
        default=5000, description="单个工具结果阈值 tokens 数"
    )
    tolerance_tokens: int = Field(
        default=6000, description="单个工具结果容忍的 tokens 数"
    )
    summary_max_tokens: int = Field(
        default=2000, description="单个工具结果摘要最大 tokens 数"
    )
    message_summary_threshold_tokens: int = Field(
        default=2000,
        description="窗口内单条工具消息超过该 token 数时用 summary/截断参与组装",
    )
    markdown_chunk_size: int = Field(
        default=1000,
        description="Markdown 分块大小（字符），用于相关性过滤",
    )
    markdown_chunk_overlap: int = Field(
        default=200,
        description="Markdown 分块重叠（字符）",
    )


class HistoryWindowConfig(BaseModel):
    """历史消息窗口配置"""

    max_tokens: int = Field(
        default=32000,
        description="历史消息 token 预算，超出部分从更早消息起截断",
    )
    max_rounds: int = Field(
        default=5,
        description="历史最多保留轮数（一轮 = 一条 user + 对应 assistant 及其中 tool）",
    )


class WindowOutSummaryConfig(BaseModel):
    """窗口外摘要管道配置（截断→摘要→user_context→system 注入）"""

    enabled: bool = Field(
        default=True,
        description="是否开启窗口外消息摘要管道",
    )
    summary_max_tokens: int = Field(
        default=1000,
        description="窗口外摘要最大 token 数，写入与注入时共用",
    )


class MemoryConfig(BaseModel):
    """Mem0 记忆服务配置（ChatContextConfig 下）。base_url 留空表示不调用 Mem0。"""

    base_url: str = Field(
        default="", description="Mem0 API 根地址；留空则禁用记忆 HTTP 调用"
    )
    search_limit: int = Field(
        default=10,
        description="搜索记忆条数上限",
    )
    search_threshold: float = Field(
        default=0.5,
        description="搜索记忆阈值",
    )


class ChatContextConfig(BaseModel):
    """对话上下文配置（层级结构）"""

    enabled: bool = Field(default=True, description="是否启用上下文压缩")
    tool_round_context_limit_ratio: float = Field(
        default=0.8,
        gt=0,
        le=1,
        description="多轮工具调用时，累计上下文超过模型上限该比例后停止继续调工具并转最终回答",
    )

    tool_result_compression: ToolResultCompressionConfig = Field(
        default_factory=ToolResultCompressionConfig,
        description="工具结果压缩与摘要",
    )
    history_window: HistoryWindowConfig = Field(
        default_factory=HistoryWindowConfig,
        description="历史消息窗口",
    )
    window_out_summary: WindowOutSummaryConfig = Field(
        default_factory=WindowOutSummaryConfig,
        description="窗口外摘要管道",
    )
    memory_config: MemoryConfig = Field(
        default_factory=MemoryConfig,
        description="Mem0 记忆服务配置；base_url 非空时启用记忆写入与检索",
    )


class SandboxConfig(BaseModel):
    """Shell 沙箱执行配置"""

    enabled: bool = Field(default=True, description="是否启用沙箱执行")
    backend: str = Field(
        default="local",
        description="沙箱后端：docker 或 local（backend=docker 时 Docker 不可用将直接失败，不回退）",
    )
    image: str = Field(default="ubuntu:22.04", description="Docker 沙箱镜像")
    cpu_limit: float = Field(default=1.0, description="CPU 限制（核数）")
    memory_limit: str = Field(default="512m", description="内存限制")
    pid_limit: int = Field(default=100, description="最大进程数")
    timeout: int = Field(
        default=600000,
        description="默认超时（毫秒，最大 600000）",
    )
    network_enabled: bool = Field(default=False, description="Docker 沙箱是否允许网络")
    container_pool_size: int = Field(
        default=5,
        description="容器预热池大小（预留，尚未实现）",
    )
    output_limit: int = Field(
        default=50000,
        description="输出截断前的最大字符数",
    )


class WechatConfig(BaseModel):
    """微信配置（微信开放平台网站应用）"""

    app_id: str = Field(..., description="微信开放平台 AppID")
    app_secret: str = Field(..., description="微信开放平台 AppSecret")

"""配置模型定义"""

from typing import Any, Literal

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
    context_limit: int = Field(gt=0, description="模型上下文 token 上限")


class EmbeddingModelConfig(BaseLLMModelConfig):
    """Embedding 模型 API 配置"""

    embedding_dimension: int = Field(default=1024, description="Embedding 维度")


class LLMConfig(BaseModel):
    """LLM 模型 API 配置（ModelResolver 解析得到的运行时配置）"""

    api_key: str = Field(description="LLM API 密钥")
    api_base: str = Field(description="LLM API 基础地址")
    model_name: str = Field(description="默认模型名称")
    context_limit: int = Field(gt=0, description="模型上下文 token 上限")
    max_output_tokens: int = Field(
        gt=0,
        description="模型输出 token 预留（显式配置或按 context_limit 推断）",
    )
    title: str | None = Field(default=None, description="展示标题（可选）")
    description: str | None = Field(default=None, description="说明文案（可选）")
    image_support: bool = Field(
        default=True, description="是否支持图片输入（多模态视觉）"
    )


ModelCapability = Literal["text", "image"]


def _default_capabilities() -> list[ModelCapability]:
    return ["text"]


class ProviderModelMeta(BaseModel):
    """Provider 下单个模型的元数据"""

    name: str | None = Field(default=None, description="展示标题（可选）")
    description: str | None = Field(default=None, description="说明文案（可选）")
    context_limit: int = Field(gt=0, description="模型上下文 token 上限")
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        description="模型输出 token 上限；为空时按 context_limit 推断",
    )
    capabilities: list[ModelCapability] = Field(
        default_factory=_default_capabilities,
        description="模型能力：text（文本）、image（图片输入）",
    )


class ProviderConfig(BaseModel):
    """单个模型供应商配置（同一 base_url / api_key 下的多个模型）"""

    base_url: str = Field(description="供应商 API 基础地址")
    api_key: str = Field(description="供应商 API 密钥（明文）")
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="客户端可选参数（timeout、max_retries 等，预留）",
    )
    models: dict[str, ProviderModelMeta] = Field(
        description="该供应商下模型（API model_name -> 元数据）"
    )


class ScenarioConfig(BaseModel):
    """场景模型选择配置"""

    description: str | None = Field(default=None, description="场景说明（可选）")
    default_model: str = Field(description="默认模型引用（provider/model_name）")
    alternatives: list[str] = Field(
        default_factory=list,
        description="可选模型引用列表（provider/model_name）",
    )


class ModelsConfig(BaseModel):
    """模型配置（供应商 + 场景两层结构）"""

    providers: dict[str, ProviderConfig] = Field(
        description="供应商配置（provider_name -> ProviderConfig）"
    )
    scenarios: dict[str, ScenarioConfig] = Field(
        description="场景配置（scenario_name -> ScenarioConfig）"
    )


class LangfuseConfig(BaseModel):
    """Langfuse 可观测配置（自托管）"""

    enabled: bool = Field(default=False, description="是否启用 Langfuse 追踪")
    host: str = Field(default="", description="Langfuse 服务地址")
    public_key: str = Field(default="", description="Langfuse Public Key")
    secret_key: str = Field(default="", description="Langfuse Secret Key")
    sample_rate: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="采样率（0~1）",
    )
    debug: bool = Field(default=False, description="是否开启 Langfuse SDK 调试日志")
    environment: str = Field(default="dev", description="环境标识，如 dev/prod")
    project_id: str = Field(
        default="",
        description="Langfuse Project ID，用于拼装 Trace UI 链接",
    )
    bad_case_dataset_name: str = Field(
        default="chat-agent-bad-cases",
        description="Bad Case 推送的固定 Dataset 名称",
    )
    report_images: bool = Field(
        default=False,
        description="是否允许 base64 图片随 trace 上报（关闭时统一脱敏为 [image omitted]）",
    )


class LLMReliabilityConfig(BaseModel):
    """LLM 调用重试与熔断配置（仅作用于 create 建连阶段）"""

    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        description="最大尝试次数（含首次）",
    )
    retry_base_delay_ms: int = Field(
        default=1000,
        ge=0,
        description="指数退避基础延迟（毫秒）",
    )
    retry_cap_delay_ms: int = Field(
        default=8000,
        ge=0,
        description="指数退避最大延迟（毫秒）",
    )
    circuit_failure_threshold: int = Field(
        default=5,
        ge=1,
        description="连续 transient/busy 失败多少次后打开熔断",
    )
    circuit_recovery_timeout_sec: int = Field(
        default=30,
        ge=1,
        description="熔断打开后冷却秒数，到期进入 half-open 探针",
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

    mcp_servers 字段控制加载哪些 MCP Server 及其传输方式。
    留空时使用内置默认值（所有本地 Server + context7 远程 Server）。
    通过设置 enabled: false 可禁用单个 Server，无需删除代码。
    """

    mcp_servers: dict[str, MCPServerEntry] = Field(
        default_factory=lambda: {
            "time": MCPServerEntry(
                module="app.mcp.mcp_servers.time_mcp.server",
            ),
            "context7": MCPServerEntry(
                transport="http",
            ),
            "weather": MCPServerEntry(
                module="app.mcp.mcp_servers.weather_mcp.server",
            ),
            "tavily": MCPServerEntry(
                module="app.mcp.mcp_servers.tavily_mcp.server",
            ),
            "code": MCPServerEntry(
                module="app.mcp.mcp_servers.code_exec_mcp.server",
            ),
            "file": MCPServerEntry(
                module="app.mcp.mcp_servers.file_mcp.server",
            ),
            "skill_manager": MCPServerEntry(
                module="app.mcp.mcp_servers.skill_manager_mcp.server",
            ),
            "shell": MCPServerEntry(
                module="app.mcp.mcp_servers.shell_mcp.server",
            ),
        },
        description="MCP Server 接入配置（server_name -> MCPServerEntry）",
    )
    normal_mode_servers: list[str] = Field(
        default_factory=lambda: [
            "time",
            "weather",
            "tavily",
            "code",
            "context7",
            "zread",
        ],
        description="普通对话（agent_mode=0）下暴露给 LLM 的 MCP Server 名称列表",
    )
    agent_mode_servers: list[str] = Field(
        default_factory=lambda: [
            "file",
            "skill_manager",
            "shell",
            "tavily",
            "context7",
            "zread",
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


class RedisConfig(BaseModel):
    """Redis 服务连接配置"""

    host: str = Field(description="Redis 主机")
    port: int = Field(description="Redis 端口")
    username: str = Field(description="Redis ACL 用户名")
    password: str = Field(description="Redis 密码")
    max_connections: int = Field(
        default=50,
        gt=0,
        description="异步连接池最大连接数",
    )
    socket_connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="连接建立超时（秒）",
    )


class CacheConfig(BaseModel):
    """业务 L2（Redis）Cache-Aside 策略配置"""

    user_detail_ttl_seconds: int = Field(
        default=60,
        gt=0,
        description="用户详情缓存 TTL（秒）",
    )
    operation_timeout_seconds: float = Field(
        default=0.5,
        gt=0,
        description="L2 GET/SET/UNLINK 单次操作超时（秒），短于 SSE XREAD socket_timeout",
    )


class ChatStreamConfig(BaseModel):
    """SSE 断点续传（Redis Stream）与 turn 幂等相关配置"""

    sse_stream_ttl_seconds: int = Field(
        default=7200,
        gt=0,
        description="活跃 SSE 流 TTL（stream/meta/seq 同步过期，秒）",
    )
    sse_stream_closed_ttl_seconds: int = Field(
        default=1800,
        gt=0,
        description="流 close 后 TTL（秒）",
    )
    sse_stream_xread_block_ms: int = Field(
        default=1000,
        gt=0,
        description="XREAD BLOCK 超时（毫秒）",
    )
    sse_stream_cancel_poll_ms: int = Field(
        default=1000,
        gt=0,
        description="Producer 轮询 Redis status=stopped 间隔（毫秒）",
    )
    turn_idempotency_ttl_seconds: int = Field(
        default=7200,
        gt=0,
        description="client_turn_id 幂等记录 TTL（秒）",
    )
    turn_idempotency_pending_ttl_seconds: int = Field(
        default=60,
        gt=0,
        description="幂等 reserve 占位 TTL（秒）",
    )
    turn_idempotency_wait_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="loser 等待 winner 写回幂等记录的超时（秒）",
    )


class MinerUConfig(BaseModel):
    """MinerU SaaS 文档转 Markdown 配置"""

    enabled: bool = Field(default=True, description="是否启用 MinerU 自动转 Markdown")
    api_url: str = Field(
        default="https://mineru.net",
        description="MinerU API 地址",
    )
    api_key: str = Field(
        default="",
        description="MinerU API Bearer Token（从 Nacos 注入）",
    )
    model_version: str = Field(
        default="vlm",
        description="MinerU 模型版本：pipeline / vlm / MinerU-HTML",
    )
    poll_interval_seconds: float = Field(
        default=3.0,
        gt=0,
        description="任务状态轮询间隔（秒）",
    )
    poll_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
        description="任务轮询总超时（秒）",
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
        default=8,
        ge=1,
        description="会话 RAG 检索 Top-K",
    )
    short_doc_max_tokens: int = Field(
        default=10000,
        ge=1,
        description="判定短文档的 token 阈值；短文档可注入全文",
    )


# ---- 上下文压缩子配置 ----
class ToolResultCompressionConfig(BaseModel):
    """工具结果压缩与摘要配置"""

    enabled: bool = Field(default=True, description="是否启用工具结果压缩与摘要")
    threshold_tokens: int = Field(
        default=5000, description="单个工具结果阈值 tokens 数"
    )
    tolerance_tokens: int = Field(
        default=8000, description="单个工具结果容忍的 tokens 数"
    )
    summary_max_tokens: int = Field(
        default=2000, description="单个工具结果摘要最大 tokens 数"
    )
    message_summary_threshold_tokens: int = Field(
        default=2000,
        description="窗口内单条工具消息超过该 token 数时用 summary/截断参与组装",
    )
    tool_arg_max_chars: int = Field(
        default=500,
        gt=0,
        description=(
            "窗口内历史 tool_use：整段 arguments_text 超过该字符数时才进入截断"
            "（对齐 hermes Pass-3 门闩）"
        ),
    )
    tool_arg_keep_chars: int = Field(
        default=200,
        gt=0,
        description=("截断时 JSON 内字符串叶子保留的前缀字符数，后缀为 ...[truncated]"),
    )
    markdown_chunk_size: int = Field(
        default=1024,
        description="Markdown 分块大小（字符），用于相关性过滤",
    )
    markdown_chunk_overlap: int = Field(
        default=200,
        description="Markdown 分块重叠（字符）",
    )
    embedding_batch_size: int = Field(
        default=10,
        gt=0,
        description="FAISS 向量化单批文档数（DashScope 限制每次最多 10 个）",
    )
    embedding_max_workers: int = Field(
        default=5,
        gt=0,
        description="FAISS 分批向量化时的最大并行线程数",
    )


def _default_tool_result_hard_limit_overrides() -> dict[str, int]:
    return {
        "exec": 20_000,
        "search_files": 20_000,
        "web_site_crawl": 20_000,
        "web_pages_extract": 25_000,
        "load_skill": 0,
    }


class ToolResultHardLimitConfig(BaseModel):
    """工具结果硬上限：Agent 超阈值落盘预览；非 Agent 原样放行由统一守卫兜底。"""

    enabled: bool = Field(default=True, description="是否启用工具结果硬上限")
    turn_budget_chars: int = Field(
        default=80_000,
        ge=0,
        description="同轮全部工具结果 content 合计字符上限（仅 Agent 模式）",
    )
    max_chars: int = Field(
        default=30_000,
        ge=0,
        description="单条工具结果默认硬上限（字符）；可被 tool_overrides 覆盖；仅 Agent",
    )
    preview_head_chars: int = Field(
        default=2_000,
        ge=0,
        description=(
            "Agent 落盘预览与落盘失败/force 截断的头部字符数；"
            "落盘失败非 force 时亦作 max_chars 头尾分配比例"
        ),
    )
    preview_tail_chars: int = Field(
        default=1_000,
        ge=0,
        description=(
            "Agent 落盘预览与落盘失败/force 截断的尾部字符数；"
            "落盘失败非 force 时亦作 max_chars 头尾分配比例"
        ),
    )
    persist_subdir: str = Field(
        default="tool-results",
        description="落盘子目录，相对 conversation workspace/",
    )
    exempt_bare_names: list[str] = Field(
        default_factory=lambda: ["read_file"],
        description=(
            "完全跳过硬上限的工具 bare 名（含同轮 force）；"
            "用于防 persist↔read 循环；体积由工具自身限制（如 read_file 的 limit）"
        ),
    )
    tool_overrides: dict[str, int] = Field(
        default_factory=_default_tool_result_hard_limit_overrides,
        description=(
            "按工具覆盖 max_chars；键可为 LLM 名或 bare 名；"
            "值为 0 表示关闭该工具的单条硬上限（同轮预算仍可强制处理；"
            "与 exempt_bare_names 的完全豁免不同）"
        ),
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


class UnifiedContextGuardConfig(BaseModel):
    """统一上下文守卫：每次 LLM 调用前按总 prompt 分级降级。"""

    enabled: bool = Field(default=True, description="是否启用统一上下文守卫")
    buffer_tokens: int = Field(
        default=13000,
        ge=0,
        description="安全缓冲 token 数（对齐 claude-code AUTOCOMPACT_BUFFER_TOKENS）",
    )
    max_output_tokens: int = Field(
        default=8192,
        gt=0,
        description="输出预留封顶；reserved_output = min(llm.max_output_tokens, 此项)",
    )
    keep_recent_tool_results: int = Field(
        default=2,
        ge=0,
        description=(
            "当前轮 Step 4 压缩时保留的最新工具组数量"
            "（一组 = 一次 ToolUseMessage + 其后对应 ToolResultMessage）"
        ),
    )
    tool_result_compress_threshold_chars: int = Field(
        default=1000,
        ge=0,
        description="当前轮工具结果超过该字符数时才进入 size-aware 压缩",
    )
    tool_result_compress_keep_head_chars: int = Field(
        default=500,
        ge=0,
        description="Step 4 head-tail 保留的头部字符数",
    )
    tool_result_compress_keep_tail_chars: int = Field(
        default=500,
        ge=0,
        description="Step 4 head-tail 保留的尾部字符数",
    )
    anti_thrash_failure_threshold: int = Field(
        default=3,
        ge=1,
        description="连续摘要失败几次后触发反抖动保护",
    )
    anti_thrash_recovery_seconds: int = Field(
        default=300,
        ge=0,
        description="反抖动恢复窗口（秒）",
    )


class MemoryConfig(BaseModel):
    """Mem0 记忆服务配置（ChatContextConfig 下）。

    base_url 与 api_key 均非空时启用 Mem0 HTTP 调用；请求头携带 X-API-Key。
    """

    base_url: str = Field(
        default="", description="Mem0 API 根地址；留空则禁用记忆 HTTP 调用"
    )
    api_key: str = Field(
        default="",
        description="Mem0 API 密钥，通过请求头 X-API-Key 发送；留空则禁用记忆 HTTP 调用",
    )
    search_limit: int = Field(
        default=5,
        description="搜索记忆条数上限",
    )
    search_threshold: float = Field(
        default=0.1,
        description="搜索记忆阈值",
    )


class ChatContextConfig(BaseModel):
    """对话上下文配置（层级结构）"""

    enabled: bool = Field(default=True, description="是否启用上下文压缩")

    tool_result_compression: ToolResultCompressionConfig = Field(
        default_factory=ToolResultCompressionConfig,
        description="工具结果压缩与摘要",
    )
    tool_result_hard_limit: ToolResultHardLimitConfig = Field(
        default_factory=ToolResultHardLimitConfig,
        description="工具结果硬上限（落盘预览 / 头尾截断 / 同轮预算）",
    )
    unified_guard: UnifiedContextGuardConfig = Field(
        default_factory=UnifiedContextGuardConfig,
        description="统一上下文守卫（总 prompt 阈值 + 分级降级）",
    )
    window_out_summary: WindowOutSummaryConfig = Field(
        default_factory=WindowOutSummaryConfig,
        description="窗口外摘要管道",
    )
    memory_config: MemoryConfig = Field(
        default_factory=MemoryConfig,
        description="Mem0 记忆服务配置；base_url 与 api_key 均非空时启用记忆写入与检索",
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


class EvalWorkerConfig(BaseModel):
    """评估 Worker 配置"""

    enabled: bool = Field(default=True, description="是否启用评估 worker")
    schedule_cron: str = Field(
        default="0 17 * * *",
        description="定时任务 cron 表达式",
    )
    judge_model_scenario: str = Field(
        default="judge",
        description="裁判模型使用的 scenario（models.scenarios.judge）",
    )
    judge_concurrency: int = Field(default=5, description="裁判并发数")
    judge_timeout_s: float = Field(default=60.0, description="单条裁判调用超时（秒）")
    judge_low_score_threshold: int = Field(
        default=3, description="低分阈值（低于此分入 bad case 队列）"
    )
    sample_rate_high: float = Field(default=0.40, description="高风险采样比例")
    sample_rate_medium: float = Field(default=0.15, description="中风险采样比例")
    sample_rate_low: float = Field(default=0.05, description="低风险采样比例")
    quick_follow_up_threshold_s: int = Field(
        default=30, description="快速追问阈值（秒）"
    )
    high_latency_threshold_s: float = Field(
        default=30.0, description="高延迟特殊采样阈值（秒）"
    )
    lookback_hours: int = Field(default=24, description="拉取最近 N 小时的 Trace")

"""Code Execution MCP Server Configuration"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.config import MCPCacheConfig


class _Settings(BaseSettings):
    """代码执行沙箱配置"""

    # 执行超时时间（秒）
    EXECUTION_TIMEOUT: int = 10

    # CPU 时间限制（秒）
    CPU_TIME_LIMIT: int = 5

    # 内存限制（MB）
    MEMORY_LIMIT_MB: int = 128

    # 最大输出长度（字符）
    MAX_OUTPUT_LENGTH: int = 10000

    # 是否允许文件系统访问
    ALLOW_FILE_ACCESS: bool = False

    # 允许的文件系统路径（仅在 ALLOW_FILE_ACCESS=True 时生效）
    ALLOWED_PATHS: list[str] = []

    # 是否允许网络访问
    ALLOW_NETWORK_ACCESS: bool = False

    # 工具调用结果缓存配置
    cache_config: MCPCacheConfig = Field(
        default_factory=MCPCacheConfig,
        description="工具调用结果缓存配置",
    )

    # 允许的导入模块白名单（标准库 + 白名单内第三方，不含文件/网络等危险能力）
    ALLOWED_IMPORTS: list[str] = [
        # 标准库内部依赖（供 datetime 等使用）
        "_io",
        "time",
        "_datetime",
        "_pydatetime",
        # 数学与数值
        "math",
        "cmath",
        "random",
        "decimal",
        "fractions",
        "statistics",
        "numbers",
        # 日期时间
        "datetime",
        "calendar",
        # 数据结构与算法
        "collections",
        "itertools",
        "functools",
        "operator",
        "heapq",
        "bisect",
        "array",
        "copy",
        # 文本与正则
        "string",
        "re",
        "textwrap",
        "difflib",
        "pprint",
        "reprlib",
        # 编码与格式
        "json",
        "base64",
        "unicodedata",
        # 哈希与随机
        "hashlib",
        "secrets",
        "uuid",
        # 第三方（需项目已安装）
        "jwt",
        # 类型与结构
        "dataclasses",
        "enum",
        "types",
        "typing",
        # 内存 IO 与解析
        "io",
        "csv",
    ]

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
    )


config = _Settings()

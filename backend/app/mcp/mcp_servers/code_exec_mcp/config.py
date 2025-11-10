"""Code Execution MCP Server Configuration"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class CodeExecConfig(BaseSettings):
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

    # 允许的导入模块白名单
    ALLOWED_IMPORTS: list[str] = [
        "math",
        "random",
        "datetime",
        "json",
        "collections",
        "itertools",
        "functools",
        "operator",
        "string",
        "re",
        "decimal",
        "fractions",
        "statistics",
    ]

    model_config = ConfigDict(
        env_file=Path(__file__).parent / '.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        env_ignore_empty=True,
        extra='ignore'
    )


config = CodeExecConfig()

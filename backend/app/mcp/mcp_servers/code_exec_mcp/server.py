"""
Code Execution MCP Server
提供安全的 Python 代码执行服务，使用沙箱隔离确保安全性
"""

from fastmcp import FastMCP
from pydantic import Field

from .config import config
from .sandbox import CodeExecutionError, SandboxExecutor, TimeoutError

mcp = FastMCP(
    name="Code Execution MCP Service",
)

# 创建沙箱执行器实例
executor = SandboxExecutor(
    timeout=config.EXECUTION_TIMEOUT,
    cpu_time_limit=config.CPU_TIME_LIMIT,
    memory_limit_mb=config.MEMORY_LIMIT_MB,
    max_output_length=config.MAX_OUTPUT_LENGTH,
    allowed_imports=config.ALLOWED_IMPORTS,
    allow_file_access=config.ALLOW_FILE_ACCESS,
    allowed_paths=config.ALLOWED_PATHS,
    allow_network_access=config.ALLOW_NETWORK_ACCESS,
)


@mcp.tool(name="python_code_exec")
def python_code_exec(
    code: str = Field(
        ...,
        description="要执行的 Python 代码",
        examples=[
            "print(1.1 + 2.2)",  # 加法
            "print(10 - 3)",  # 减法
            "print(5 * 4)",  # 乘法
            "print(15 / 3)",  # 除法
            "print(2 ** 3)",  # 幂运算
            "print(17 % 5)",  # 取模
            "print((10 + 5) * 2)",  # 混合运算
        ],
    ),
) -> str:
    """
    安全执行 Python 代码并返回结果
    注意：此工具仅用于执行简单的计算和数据处理任务，不支持文件系统操作、网络访问和图形绘制。

    Returns:
        代码执行的输出结果（stdout）
    """
    try:
        result = executor.execute(code)
        return result
    except TimeoutError as e:
        raise TimeoutError(f"代码执行超时: {str(e)}")
    except CodeExecutionError as e:
        raise CodeExecutionError(f"代码执行失败: {str(e)}")
    except Exception as e:
        raise Exception(f"未知错误: {str(e)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Code Execution MCP Server")
    parser.add_argument(
        "--transport",
        choices=["http", "stdio"],
        default="http",
        help="传输方式：http 或 stdio",
    )
    parser.add_argument("--port", type=int, default=8004, help="HTTP 模式下的端口号")

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio 模式：通过标准输入输出与客户端通信
        mcp.run(transport="stdio")
    else:
        # HTTP 模式：启动 HTTP 服务器
        mcp.run(transport="http", port=args.port)

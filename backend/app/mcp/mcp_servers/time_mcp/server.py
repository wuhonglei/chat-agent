"""
Time MCP Server
提供当前时间查询服务
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field
from tzlocal import get_localzone_name

from app.mcp.cache import add_response_caching_if_enabled

from .config import config
from .models import TimeResponse
from .utils import format_results

# 创建 MCP 实例
mcp = FastMCP(name="Time MCP Service")

add_response_caching_if_enabled(mcp, config.cache_config)


@mcp.tool(name="get_current_time")
async def get_current_time(
    timezone: str | None = Field(
        default_factory=get_localzone_name,
        description="指定时区，如果不提供则使用本地时区。支持的格式：'Asia/Shanghai', 'America/New_York', 'Europe/London' 等",
    ),
) -> TimeResponse:
    """
    获取指定时区的当前时间

    Args:
        timezone: 时区名称，如果不提供则使用本地时区

    Returns:
        TimeResponse: 包含当前时间、时区信息和时间戳的响应
    """
    try:
        # 如果没有指定时区，使用本地时区
        if not timezone:
            timezone = get_localzone_name()

        # 创建时区对象
        tz = ZoneInfo(timezone)

        # 获取当前时间
        now = datetime.now(tz)

        # 格式化时间字符串
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

        # 计算 UTC 偏移量
        utc_offset = now.strftime("%z")

        # 获取 Unix 时间戳
        timestamp = int(now.timestamp())

        data = TimeResponse(
            structured_content=TimeResponse(
                current_time=current_time_str,
                timezone=timezone,
                utc_offset=utc_offset,
                timestamp=timestamp,
            ),
            content=format_results(data),
        )
    except Exception as e:
        # 如果指定的时区无效，使用本地时区作为后备
        local_tz = get_localzone_name()
        tz = ZoneInfo(local_tz)
        now = datetime.now(tz)

        data = TimeResponse(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            timezone=f"{timezone}(无效，使用本地时区: {local_tz})",
            utc_offset=now.strftime("%z"),
            timestamp=int(now.timestamp()),
        )
    return ToolResult(structured_content=data, content=format_results(data))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Time MCP Server")
    parser.add_argument(
        "--transport",
        choices=["http", "stdio"],
        default="http",
        help="传输方式：http 或 stdio",
    )
    parser.add_argument("--port", type=int, default=8003, help="HTTP 模式下的端口号")

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio 模式：通过标准输入输出与客户端通信
        mcp.run(transport="stdio")
    else:
        # HTTP 模式：启动 HTTP 服务器
        mcp.run(transport="http", port=args.port)

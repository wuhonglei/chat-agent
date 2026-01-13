"""
IP Locator MCP Server
提供 IP 地址定位服务
文档地址: https://ip-api.com/docs/api:json
"""

import httpx
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from .models import IPLocatorResponse
from .utils import format_results

# 创建 MCP 实例
mcp = FastMCP(name="IP Locator MCP Service")


@mcp.tool(name="locate_ip")
async def locate_ip(
    ip_address: str = Field(..., description="查询的 IP 地址"),
) -> IPLocatorResponse:
    """
    定位 IP 地址
    根据提供的 IP 地址查询地理位置信息，包括国家、地区、城市、经纬度、时区、ISP 等信息。
    """
    url = f"http://ip-api.com/json/{ip_address}"

    async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # 检查 API 返回的状态
            if data.get("status") == "fail":
                error_message = data.get("message", "查询失败")
                raise Exception(f"IP 定位查询失败: {error_message}")

            structured_content = IPLocatorResponse.model_validate(data)
            return ToolResult(
                structured_content=structured_content,
                content=format_results(structured_content),
            )
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"IP 定位查询失败: {e}")

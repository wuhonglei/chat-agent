"""
如何运行: 在 mcp_servers 目录执行 `uv run -m ip_locator_mcp.test_server`
"""

import asyncio
from fastmcp import Client

from .server import mcp
client = Client(mcp)


async def test_locate_ip():
    async with client:
        result = await client.call_tool("locate_ip", {
            "ip_address": "24.48.0.1"
        })
    print(result.data)


if __name__ == "__main__":
    asyncio.run(test_locate_ip())

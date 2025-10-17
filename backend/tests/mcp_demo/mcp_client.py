"""
MCP Client - 演示如何同时连接远程和本地 MCP 服务器
最简单的方案：使用 MCPConfigTransport 自动合并多个远程服务器 + 本地服务器挂载
"""

import asyncio
from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport, MCPConfigTransport, MCPConfig
from mcp_demo.weather_mcp.weather_server import mcp as weather_mcp
import time


async def main():
    """Main function"""
    start_time = time.time()
    # 2. 为远程 Tavily 服务器创建配置并获取其工具
    config = {
        "mcpServers": {
            "tavily-remote-mcp": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "http",
            },
            "weather-mcp": {
                "command": "python3",
                "args": ["-m", "mcp_demo.weather_mcp.weather_server", "--transport", "stdio"],
            }
        }
    }
    mcp_config = MCPConfig.from_dict(config)
    # 创建远程客户端（MCPConfigTransport 会自动添加前缀）
    client = Client(transport=mcp_config)
    async with client:
        tools = await client.list_tools()
        for tool in tools:
            print(tool.name)

        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")

        result = await client.call_tool_mcp('weather-mcp_search_city', {
            'location': '深圳'
        })
        print(result)

if __name__ == "__main__":
    asyncio.run(main())

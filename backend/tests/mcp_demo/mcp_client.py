"""
MCP Client - 演示如何同时连接远程和本地 MCP 服务器
最简单的方案：使用 MCPConfigTransport 自动合并多个远程服务器 + 本地服务器挂载
"""

import asyncio
from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport, MCPConfigTransport
from mcp_demo.weather_mcp.weather_server import mcp as weather_mcp


async def main():
    """Main function"""
    # 方案：创建一个复合服务器，挂载本地服务器，然后挂载远程配置
    composite_mcp = FastMCP("composite-server")

    # 1. 挂载本地天气 MCP 服务器
    composite_mcp.mount(weather_mcp, prefix="weather")

    # 2. 为远程 Tavily 服务器创建配置并获取其工具
    remote_config = {
        "mcpServers": {
            "tavily": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "http",
            }
        }
    }

    # 创建远程客户端（MCPConfigTransport 会自动添加前缀）
    remote_client = Client(transport=MCPConfigTransport(remote_config))

    # 3. 由于 FastMCP.mount() 只支持 FastMCP 实例，我们采用包装方案
    # 在复合服务器上挂载远程配置创建的传输层（这个传输层已经包含了前缀逻辑）
    # 注意：MCPConfigTransport 内部已经创建了一个复合服务器，我们可以直接挂载它

    async with remote_client:
        # 获取远程工具
        remote_tools = await remote_client.list_tools()
        print("\n远程 Tavily MCP 服务器工具:")
        for tool in remote_tools:
            print(f"  - {tool.name}")

    # 4. 创建本地客户端
    local_client = Client(transport=FastMCPTransport(mcp=composite_mcp))

    async with local_client:
        # 列出本地工具
        local_tools = await local_client.list_tools()
        print("\n本地天气 MCP 服务器工具:")
        for tool in local_tools:
            print(f"  - {tool.name}")

        # 测试调用本地工具
        print("\n测试调用本地天气工具:")
        try:
            result = await local_client.call_tool(
                "weather_get_weather_forecast", {
                    "city": "San Francisco", "days": 3}
            )
            print(f"天气预报: {result}")
        except Exception as e:
            print(f"调用失败: {e}")

    print(
        "\n说明：当前显示了两个独立的客户端（本地和远程）。"
    )
    print(
        "如需在单个客户端中合并，可以使用 MCPConfigTransport 管理所有远程服务器，"
    )
    print("或将本地服务器也通过 stdio/http 方式暴露后添加到配置中。"
          )


if __name__ == "__main__":
    asyncio.run(main())

"""
MCP Client
"""

import asyncio
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport, MCPConfigTransport, MCPConfig
from mcp_demo.weather_mcp.weather_server import mcp as weather_mcp


async def main():
    """Main function"""
    config = {
        "mcpServers": {
            "tavily-remote-mcp": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "http"
            },
        }
    }
    mcp_config = MCPConfig.from_dict(config)
    mcp_config.add_server("weather-mcp", weather_mcp)
    client = Client(transport=mcp_config)
    async with client:
        pass
        tools = await client.list_tools()
        for tool in tools:
            print(tool.name)

if __name__ == "__main__":
    asyncio.run(main())

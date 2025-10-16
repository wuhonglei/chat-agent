"""
Tavily MCP Demo
"""

from loguru import logger
import asyncio
import sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport, MCPConfigTransport


async def main():
    """Main function"""
    config = {
        "mcpServers": {
            "tavily-remote-mcp": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "http"
            }
        }
    }
    client = Client(transport=MCPConfigTransport(config))
    async with client:
        result = await client.call_tool_mcp("tavily_search", {
            "query": "What is the capital of France?"
        })
        print(result)

if __name__ == "__main__":
    asyncio.run(main())

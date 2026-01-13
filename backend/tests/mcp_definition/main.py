import asyncio

from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport

mcp = FastMCP("Demo 🚀")


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


async def main():
    # 列出所有工具
    client = Client(transport=FastMCPTransport(mcp), init_timeout=5.0)
    async with client:
        tools = await client.list_tools()
        print(tools[0])


if __name__ == "__main__":
    asyncio.run(main())

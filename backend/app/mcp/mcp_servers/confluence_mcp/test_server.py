import asyncio
from fastmcp import Client

from .config import config
from .server import mcp

client = Client(mcp)


async def test_search():
    async with client:
        result = await client.call_tool("confluence_search", {
            "query": "siteSearch ~ \"ai agent\"",
            "limit": 3
        })
    print(result)


async def main():
    await test_search()

if __name__ == "__main__":
    asyncio.run(main())

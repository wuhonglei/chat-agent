import asyncio
from pprint import pprint

from fastmcp import Client

from .server import mcp

client = Client(mcp)


async def test_search():
    async with client:
        result = await client.call_tool(
            "shopee_confluence_search", {"query": 'siteSearch ~ "ai agent"', "limit": 3}
        )
    pprint(result.data)


async def test_get_page_children():
    async with client:
        result = await client.call_tool(
            "shopee_confluence_get_page_children", {"parent_id": "106730201"}
        )
    pprint(result.data)


async def test_get_page_content():
    async with client:
        result = await client.call_tool("shopee_confluence_get_page", {"page_id": "2923648424"})
    print(result.data)


async def main():
    await test_search()
    await test_get_page_children()
    await test_get_page_content()


if __name__ == "__main__":
    asyncio.run(main())

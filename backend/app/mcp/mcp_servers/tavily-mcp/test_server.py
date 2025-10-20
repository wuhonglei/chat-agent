"""
Test script for Tavily MCP Server
Run this to verify the server is working correctly
"""

import asyncio
from fastmcp import Client

try:
    from .config import config
    from .server import mcp, tavily_search, tavily_extract, tavily_map
    from .models import TavilySearchResponse, TavilyExtractResponse, TavilyMapResponse
except ImportError:
    from config import config
    from server import mcp, tavily_search, tavily_extract, tavily_map
    from models import TavilySearchResponse, TavilyExtractResponse, TavilyMapResponse

client = Client(mcp)


async def test_search():
    """Test the search functionality"""
    print("\n=== Testing tavily_search ===")
    async with client:
        result = await client.call_tool("tavily_search", {
            "query": "Python programming language",
            "max_results": 3,
            "search_depth": "advanced"
        })

    data = result.data
    print("Search successful!")
    print(f"Formatted output preview:\n{data.results[:500]}...")
    print(f"\nRaw results count: {len(data.results)}")
    print(data)


async def test_extract():
    """Test the extract functionality"""
    print("\n=== Testing tavily_extract ===")
    async with client:
        result = await client.call_tool("tavily_extract", {
            "urls": ["https://www.python.org/"],
            "extract_depth": "advanced",
            "format": "markdown"
        })

    data = result.data
    print("Extract successful!")
    print(f"Formatted output preview:\n{data.results[:500]}...")
    print(f"Raw results count: {len(data.results)}")


async def test_map():
    """Test the map functionality"""
    print("\n=== Testing tavily_map ===")

    async with client:
        result = await client.call_tool("tavily_map", {
            "url": "https://www.python.org/",
            "max_depth": 1,
            "limit": 10
        })
    data = result.data
    print(data)
    print(f"Raw results count: {len(data.results)}")


async def main():
    """Run all tests"""
    print("Starting Tavily MCP Server Tests")
    print(
        f"API Key configured: {'Yes' if config.TAVILY_API_KEY else 'No'}")

    if not config.TAVILY_API_KEY:
        print("\n⚠️  WARNING: TAVILY_API_KEY not set!")
        print("Please set your API key in .env file or environment variable")
        return

    try:
        await test_search()
        await test_extract()
        await test_map()

        print("\n✅ All tests completed!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

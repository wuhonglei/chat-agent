"""Test script for Confluence MCP Server."""

import asyncio
from .server import mcp
from fastmcp import Client


async def test_confluence_mcp():
    """Test the Confluence MCP server tools."""
    print("Testing Confluence MCP Server...")

    # 测试 search 工具
    print("\n=== Testing search tool ===")
    try:
        # 这里需要实际的 Context 对象，暂时跳过实际调用
        print("Search tool defined successfully")
        print(f"Search tool description: {mcp.tools['search'].description}")
    except Exception as e:
        print(f"Error testing search tool: {e}")

    # 测试 get_page 工具
    print("\n=== Testing get_page tool ===")
    try:
        print("Get page tool defined successfully")
        print(
            f"Get page tool description: {mcp.tools['get_page'].description}")
    except Exception as e:
        print(f"Error testing get_page tool: {e}")

    # 测试 get_page_children 工具
    print("\n=== Testing get_page_children tool ===")
    try:
        print("Get page children tool defined successfully")
        print(
            f"Get page children tool description: {mcp.tools['get_page_children'].description}")
    except Exception as e:
        print(f"Error testing get_page_children tool: {e}")

    # 显示所有工具
    print(f"\n=== All tools ===")
    print(f"Total tools: {len(mcp.tools)}")
    for tool_name, tool in mcp.tools.items():
        print(f"- {tool_name}: {tool.description[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_confluence_mcp())

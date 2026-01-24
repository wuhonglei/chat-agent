"""
Context7 MCP 连通性测试
需在项目根目录或设置 PYTHONPATH 后执行：
  python -m app.mcp.mcp_servers.context7_mcp.test_server
"""

import asyncio

from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport

from .config import config
from .server import mcp

client = Client(transport=FastMCPTransport(mcp))


async def main() -> None:
    print("Context7 MCP 连通性测试")
    print(f"  URL: {config.url}")
    print(f"  API Key: {'已配置' if config.headers.get('CONTEXT7_API_KEY') else '未配置'}")
    print(f"  缓存: {'开启' if config.cache_config.cache_enabled else '关闭'}\n")

    if not config.headers.get("CONTEXT7_API_KEY"):
        print("请设置 CONTEXT7_API_KEY（.env 或环境变量）")
        return

    try:
        async with client:
            tools = await client.list_tools()
        print(f"list_tools 成功，工具数: {len(tools)}")
        for t in tools[:5]:
            print(f"  - {t.name}: {t.description[:60] if t.description else ''}...")
        if len(tools) > 5:
            print(f"  ... 等共 {len(tools)} 个")
        print("\n✅ 连通性正常")
    except Exception as e:
        print(f"\n❌ 失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())

"""
测试 Time MCP Server
"""
from app.mcp.mcp_servers.time_mcp.server import mcp
import asyncio
from fastmcp import Client


async def test_time_tool():
    """测试时间工具功能"""

    print("测试 Time MCP Server...")

    # 创建客户端
    client = Client(mcp)

    try:
        async with client:
            # 测试获取本地时间
            print("\n1. 测试获取本地时间:")
            result = await client.call_tool("get_current_time", {})
            print(f"结果: {result}")

            # 测试获取指定时区时间
            print("\n2. 测试获取上海时区时间:")
            result = await client.call_tool("get_current_time", {"timezone": "Asia/Shanghai"})
            print(f"结果: {result}")

            # 测试获取纽约时区时间
            print("\n3. 测试获取纽约时区时间:")
            result = await client.call_tool("get_current_time", {"timezone": "America/New_York"})
            print(f"结果: {result}")

            # 测试无效时区（应该回退到本地时区）
            print("\n4. 测试无效时区:")
            result = await client.call_tool("get_current_time", {"timezone": "Invalid/Timezone"})
            print(f"结果: {result}")

            print("\n✅ 所有测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_time_tool())

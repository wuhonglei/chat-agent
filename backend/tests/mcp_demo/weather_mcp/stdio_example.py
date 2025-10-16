"""
Stdio 协议使用示例
演示如何通过 stdio 协议调用 MCP server
"""

import asyncio
import subprocess
import sys
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport, UvStdioTransport
import json


async def test_stdio_client():
    """测试 stdio 模式的客户端"""
    print("🌤️ 测试 Stdio 模式的 MCP Client")
    print("=" * 50)

    try:
        # 使用 PythonStdioTransport 连接到 server
        transport = PythonStdioTransport(
            script_path="weather_server.py",
            args=["--transport", "stdio"]
        )

        # 创建客户端
        client = Client(transport=transport)

        async with client:
            print("✅ 成功连接到 stdio server")

            # 测试工具调用
            print("\n1. 测试城市搜索...")
            result = await client.call_tool(
                name="search_city",
                arguments={
                     "location": "北京",
                    "number": 3
                })
            print(result)
            print(f"搜索结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

            print("\n2. 测试实时天气...")
            result = await client.call_tool("get_current_weather", {
                "location": "101010100"
            })
            print(f"实时天气: {json.dumps(result, ensure_ascii=False, indent=2)}")

        print("\n✅ 测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_simple_stdio():
    """简单的 stdio 测试"""
    print("\n🔧 简单的 Stdio 测试")
    print("=" * 30)

    try:
        # 使用字符串路径创建 transport（会自动推断为 PythonStdioTransport）
        # 注意：直接使用脚本路径，参数会在 PythonStdioTransport 中处理
        client = Client(transport=UvStdioTransport(
            command="python3",
            args=["weather_server.py", "--transport", "stdio"],
        ))

        async with client:
            print("✅ 成功连接到 stdio server")

            # 获取可用工具列表
            print("\n可用工具:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            # 测试一个简单的工具调用
            print("\n测试城市搜索...")
            result = await client.call_tool("search_city", {
                "location": "上海",
                "number": 2
            })
            # 处理 CallToolResult 对象
            if hasattr(result, 'content') and result.content:
                content = result.content[0].text if result.content else "无内容"
                try:
                    # 尝试解析 JSON 内容
                    import json
                    parsed_content = json.loads(content)
                    print(
                        f"搜索结果: {json.dumps(parsed_content, ensure_ascii=False, indent=2)}")
                except json.JSONDecodeError:
                    print(f"搜索结果: {content}")
            else:
                print(f"搜索结果: {result}")

        print("\n✅ 简单测试完成！")

    except Exception as e:
        print(f"❌ 简单测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stdio 协议测试")
    parser.add_argument("--mode", choices=["client", "simple"], default="simple",
                        help="测试模式：client 或 simple")

    args = parser.parse_args()

    if args.mode == "client":
        asyncio.run(test_stdio_client())
    else:
        asyncio.run(test_simple_stdio())

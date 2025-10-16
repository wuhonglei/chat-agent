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
from pathlib import Path

current_dir = Path(__file__).parent


def get_result_data(result):
    data = getattr(result, 'data', None)
    if data:
        return json.dumps(data, ensure_ascii=False, indent=2)
    return None


async def test_simple_stdio():
    """简单的 stdio 测试"""
    print("\n🔧 简单的 Stdio 测试")
    print("=" * 30)

    try:
        # 使用字符串路径创建 transport（会自动推断为 PythonStdioTransport）
        # 注意：直接使用脚本路径，参数会在 PythonStdioTransport 中处理
        server_path = current_dir / "weather_server.py"
        client = Client(transport=UvStdioTransport(
            command="python3",
            args=[str(server_path), "--transport", "stdio"],
        ))

        async with client:
            print("✅ 成功连接到 stdio server")

            # 获取可用工具列表
            print("\n可用工具:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            print("\n1. 测试搜索城市...")
            result = await client.call_tool("search_city", {
                "location": "深圳"
            })
            data = get_result_data(result)
            print(f"搜索城市: {data}")

            location_id = result.data['location'][0]['id']

            print("\n2. 测试当前天气...")
            result = await client.call_tool("get_current_weather", {
                "location": location_id,
                "lang": "zh",
                "unit": "m"
            })
            data = get_result_data(result)
            print(f"当前天气: {data}")

            print("\n3. 测试天气预报...")
            result = await client.call_tool("get_weather_forecast", {
                "location": location_id,
                "days": "7d"
            })
            data = get_result_data(result)
            print(f"天气预报: {data}")

            print("\n4. 测试天气预警...")
            result = await client.call_tool("get_weather_alerts", {
                "location": location_id,
            })
            data = get_result_data(result)
            print(f"天气预警: {data}")

            print("\n5. 测试空气质量...")
            result = await client.call_tool("get_air_quality", {
                "location": location_id,
            })
            data = get_result_data(result)
            print(f"空气质量: {data}")

        print("\n✅ 简单测试完成！")

    except Exception as e:
        print(f"❌ 简单测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stdio 协议测试")
    args = parser.parse_args()
    asyncio.run(test_simple_stdio())

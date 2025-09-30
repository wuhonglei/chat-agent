"""
和风天气 MCP Client
用于调用和风天气 MCP Server 的工具
"""

import asyncio
from fastmcp import Client


class WeatherClient:
    """和风天气 MCP 客户端"""

    def __init__(self, server_url: str = "http://localhost:8000/mcp", transport: str = "http"):
        """
        初始化客户端

        Args:
            server_url: HTTP 模式下的服务器地址（仅 HTTP 模式需要）
            transport: 传输方式，"http" 或 "stdio"
        """
        self.transport = transport
        if transport == "stdio":
            # Stdio 模式：不需要 URL，通过进程管道通信
            self.client = Client(transport="stdio")
        else:
            # HTTP 模式：需要服务器 URL
            self.client = Client(server_url)

    async def search_city(self, location: str, adm: str = "", range: str = "cn",
                          number: int = 10, lang: str = "zh"):
        """搜索城市位置信息"""
        async with self.client:
            result = await self.client.call_tool("search_city", {
                "location": location,
                "adm": adm,
                "range": range,
                "number": number,
                "lang": lang
            })
            return result

    async def get_current_weather(self, location: str, lang: str = "zh", unit: str = "m"):
        """获取实时天气信息"""
        async with self.client:
            result = await self.client.call_tool("get_current_weather", {
                "location": location,
                "lang": lang,
                "unit": unit
            })
            return result

    async def get_weather_forecast(self, location: str, days: str = "7d",
                                   lang: str = "zh", unit: str = "m"):
        """获取天气预报信息"""
        async with self.client:
            result = await self.client.call_tool("get_weather_forecast", {
                "location": location,
                "days": days,
                "lang": lang,
                "unit": unit
            })
            return result

    async def get_weather_alerts(self, location: str, lang: str = "zh"):
        """获取天气预警信息"""
        async with self.client:
            result = await self.client.call_tool("get_weather_alerts", {
                "location": location,
                "lang": lang
            })
            return result

    async def get_air_quality(self, location: str, lang: str = "zh"):
        """获取空气质量信息"""
        async with self.client:
            result = await self.client.call_tool("get_air_quality", {
                "location": location,
                "lang": lang
            })
            return result


async def test_weather_client(transport: str = "http"):
    """测试天气客户端功能"""
    print("🌤️ 和风天气 MCP Client 测试")
    print(f"传输模式: {transport}")
    print("=" * 50)

    # 创建客户端实例
    weather_client = WeatherClient(transport=transport)

    try:
        # 测试城市搜索
        print("\n1. 测试城市搜索...")
        city_result = await weather_client.search_city(location="北京")
        print(f"搜索结果: {city_result}")

        # 测试实时天气（使用北京的 LocationID）
        print("\n2. 测试实时天气查询...")
        weather_result = await weather_client.get_current_weather(location="101010100")
        print(f"实时天气: {weather_result}")

        # 测试天气预报
        print("\n3. 测试天气预报查询...")
        forecast_result = await weather_client.get_weather_forecast(location="101010100", days="3d")
        print(f"3天预报: {forecast_result}")

        # 测试天气预警
        print("\n4. 测试天气预警查询...")
        alerts_result = await weather_client.get_weather_alerts(location="101010100")
        print(f"天气预警: {alerts_result}")

        # 测试空气质量
        print("\n5. 测试空气质量查询...")
        air_result = await weather_client.get_air_quality(location="101010100")
        print(f"空气质量: {air_result}")

        print("\n✅ 测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("请确保：")
        print("1. weather_server.py 正在运行")
        print("2. 已设置正确的环境变量 QWEATHER_API_KEY")
        print("3. 网络连接正常")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="和风天气 MCP Client 测试")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http",
                        help="传输方式：http 或 stdio")

    args = parser.parse_args()

    # 运行测试
    asyncio.run(test_weather_client(args.transport))

"""
和风天气 MCP Server 测试脚本
"""

import asyncio
import os
import httpx
from typing import Dict, Any
from config import config

# 直接实现天气查询函数，避免 MCP 装饰器问题


async def make_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """发送 HTTP 请求到和风天气 API"""
    base_url = config.QWEATHER_BASE_URL
    api_key = config.QWEATHER_API_KEY
    url = f"{base_url}{endpoint}"
    params["key"] = api_key

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"请求处理失败: {e}")


async def search_city(
    location: str,
    adm: str = "",
    range: str = "cn",
    number: int = 10,
    lang: str = "zh",
) -> Dict[str, Any]:
    """搜索城市位置信息"""
    params = {
        "location": location,
        "adm": adm,
        "range": range,
        "number": min(number, 20),
        "lang": lang
    }

    try:
        data = await make_request("/v2/city/lookup", params)
        return data
    except Exception as e:
        return {"error": str(e)}


async def get_current_weather(
    location: str,
    lang: str = "zh",
    unit: str = "m",
) -> Dict[str, Any]:
    """获取实时天气信息"""

    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

    try:
        data = await make_request("/v7/weather/now", params)
        return data
    except Exception as e:
        return {"error": str(e)}


async def get_weather_forecast(
    location: str,
    days: str = "7d",
    lang: str = "zh",
    unit: str = "m",
) -> Dict[str, Any]:
    """获取天气预报信息"""

    # 验证天数参数
    valid_days = ["3d", "7d", "10d", "15d", "30d"]
    if days not in valid_days:
        return {"error": f"无效的天数参数，支持: {', '.join(valid_days)}"}

    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

    try:
        data = await make_request(f"/v7/weather/{days}", params)
        return data
    except Exception as e:
        return {"error": str(e)}


async def get_weather_alerts(
    location: str,
    lang: str = "zh",
) -> Dict[str, Any]:
    """获取天气预警信息"""

    params = {
        "location": location,
        "lang": lang
    }

    try:
        data = await make_request("/v7/warning/now", params)
        return data
    except Exception as e:
        return {"error": str(e)}


async def get_air_quality(
    location: str,
    lang: str = "zh",
) -> Dict[str, Any]:
    """获取空气质量信息"""

    params = {
        "location": location,
        "lang": lang
    }

    try:
        data = await make_request("/v7/air/now", params)
        return data
    except Exception as e:
        return {"error": str(e)}


async def test_weather_functions():
    """测试天气查询功能"""
    print("🌤️ 和风天气 MCP Server 测试")
    print("=" * 50)

    # 测试城市搜索
    print("\n1. 测试城市搜索...")
    try:
        city_result = await search_city(location="北京")
        print(f"搜索结果: {city_result}")
    except Exception as e:
        print(f"城市搜索失败: {e}")

    # 测试实时天气（使用北京的 LocationID）
    print("\n2. 测试实时天气查询...")
    try:
        weather_result = await get_current_weather(location="101010100")
        print(f"实时天气: {weather_result}")
    except Exception as e:
        print(f"实时天气查询失败: {e}")

    # 测试天气预报
    print("\n3. 测试天气预报查询...")
    try:
        forecast_result = await get_weather_forecast(location="101010100", days="3d")
        print(f"3天预报: {forecast_result}")
    except Exception as e:
        print(f"天气预报查询失败: {e}")

    # 测试天气预警
    print("\n4. 测试天气预警查询...")
    try:
        alerts_result = await get_weather_alerts(location="101010100")
        print(f"天气预警: {alerts_result}")
    except Exception as e:
        print(f"天气预警查询失败: {e}")

    # 测试空气质量
    print("\n5. 测试空气质量查询...")
    try:
        air_result = await get_air_quality(location="101010100")
        print(f"空气质量: {air_result}")
    except Exception as e:
        print(f"空气质量查询失败: {e}")

    print("\n✅ 测试完成！")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_weather_functions())

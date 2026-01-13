"""
和风天气 MCP Server
基于和风天气 API 提供天气查询服务
文档地址: https://dev.qweather.com/docs/start/
"""

from typing import Any

import httpx
from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport
from pydantic import Field

try:
    # 尝试相对导入（当作为模块运行时）
    from .config import config
    from .models import (
        City,
        CitySearchResponse,
        WeatherAlert,
        WeatherAlertResponse,
        WeatherDaily,
        WeatherDailyResponse,
        WeatherNow,
        WeatherNowResponse,
    )
except ImportError:
    # 绝对导入（当直接运行时）
    from config import config
    from models import (
        City,
        CitySearchResponse,
        WeatherAlert,
        WeatherAlertResponse,
        WeatherDaily,
        WeatherDailyResponse,
        WeatherNow,
        WeatherNowResponse,
    )

# 创建 MCP 实例
mcp = FastMCP("weather-mcp")


async def make_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """发送 HTTP 请求到和风天气 API"""
    url = f"{config.QWEATHER_BASE_URL}{endpoint}"
    params["key"] = config.QWEATHER_API_KEY

    async with httpx.AsyncClient(timeout=config.QWEATHER_TIMEOUT) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "200":
                raise Exception(data)
            return data
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"请求处理失败: {e}")


@mcp.tool(name="search_city")
async def search_city(
    location: str = Field(..., description="需要查询地区的名称，支持文字。例如 location=北京"),
    adm: str | None = Field(
        default="",
        description="城市的上级行政区划，可设定只在某个行政区划范围内进行搜索，用于排除重名城市或对结果进行过滤。例如 adm=beijing",
    ),
    range: str | None = Field(
        default="cn",
        description="搜索范围，可设定只在某个国家或地区范围内进行搜索，国家和地区名称需使用ISO 3166 所定义的国家代码。如果不设置此参数，搜索范围将在所有城市。例如 range=cn",
    ),
    number: int | None = Field(
        default=1, description="返回结果的数量，取值范围1-20，默认返回 1 个结果。"
    ),
    lang: str | None = Field(default="zh", description="多语言设置，支持 zh（中文）、en（英文）等"),
) -> list[City]:
    """
    搜索城市信息
    """
    params = {
        "location": location,
        "adm": adm,
        "range": range,
        "number": number,
        "lang": lang,
    }

    try:
        data = await make_request("/geo/v2/city/lookup", params)
        city_search_response = CitySearchResponse.model_validate(data)
        return city_search_response.location
    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"


@mcp.tool(name="get_current_weather")
async def get_current_weather(
    location: str = Field(
        ...,
        description="位置信息，可以是 LocationID（如：101010100）或经纬度坐标（如：116.41,39.92）",
    ),
    lang: str = Field(default="zh", description="多语言设置，支持 zh（中文）、en（英文）等"),
    unit: str = Field(default="m", description="单位设置，m（公制）或 i（英制）"),
) -> WeatherNow:
    """
    获取实时天气信息
    """
    params = {"location": location, "lang": lang, "unit": unit}

    try:
        data = await make_request("/v7/weather/now", params)
        weather_now_response = WeatherNowResponse.model_validate(data)
        return weather_now_response.now
    except Exception as e:
        return f"❌ 获取天气失败: {str(e)}"


@mcp.tool(name="get_weather_forecast")
async def get_weather_forecast(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    days: str = Field(default="7d", description="预报天数，支持 3d、7d、10d、15d、30d"),
    lang: str = Field(default="zh", description="多语言设置"),
    unit: str = Field(default="m", description="单位设置（m=公制，i=英制）"),
) -> list[WeatherDaily]:
    """
    获取天气预报信息
    """
    # 验证天数参数
    valid_days = ["3d", "7d", "10d", "15d", "30d"]
    if days not in valid_days:
        return f"❌ 无效的天数参数，支持: {', '.join(valid_days)}"

    params = {"location": location, "lang": lang, "unit": unit}

    try:
        data = await make_request(f"/v7/weather/{days}", params)
        weather_daily_response = WeatherDailyResponse.model_validate(data)
        return weather_daily_response.daily
    except Exception as e:
        return f"❌ 获取预报失败: {str(e)}"


@mcp.tool(name="get_weather_alerts")
async def get_weather_alerts(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    lang: str = Field(default="zh", description="多语言设置"),
) -> list[WeatherAlert]:
    """
    获取天气预警信息
    """
    params = {"location": location, "lang": lang}

    try:
        data = await make_request("/v7/warning/now", params)
        weather_alert_response = WeatherAlertResponse.model_validate(data)
        return weather_alert_response.warning
    except Exception as e:
        return f"❌ 获取预警失败: {str(e)}"


async def main():
    client = Client(transport=FastMCPTransport(mcp))
    async with client:
        tools = await client.list_tools()
        result = await client.call_tool("search_city", {"location": "北京"})
        data = result.data
        pass
        print(result)


if __name__ == "__main__":
    # asyncio.run(main())
    import argparse

    parser = argparse.ArgumentParser(description="和风天气 MCP Server")
    parser.add_argument(
        "--transport",
        choices=["http", "stdio"],
        default="http",
        help="传输方式：http 或 stdio",
    )
    parser.add_argument("--port", type=int, default=8001, help="HTTP 模式下的端口号")

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio 模式：通过标准输入输出与客户端通信
        mcp.run(transport="stdio")
    else:
        # HTTP 模式：启动 HTTP 服务器
        mcp.run(transport="http", port=args.port)

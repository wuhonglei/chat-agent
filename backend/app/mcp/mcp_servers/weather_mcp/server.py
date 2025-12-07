"""
和风天气 MCP Server
基于和风天气 API 提供天气查询服务
文档地址: https://dev.qweather.com/docs/start/
"""

from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.tools.tool import ToolResult
from typing import List, Literal
from fastmcp import FastMCP
from pydantic import Field
from .utils import make_request, format_cities, format_current_weather, format_weather_hourly_forecast
from .utils import format_weather_daily_forecast, format_weather_alerts

# 需要在 weather_mcp 目录的上层执行: uv run -m weather_mcp.server
from .models import CitySearchResponse, WeatherHourlyResponse, WeatherNowResponse, WeatherNow, City, WeatherDaily, WeatherDailyResponse, WeatherAlertResponse, WeatherAlert, WeatherHourly

# 创建 MCP 实例
mcp = FastMCP(
    name="Weather MCP Service",
)


@mcp.tool(name="search_city")
async def search_city(
    location: str = Field(...,
                          description="需要查询地区的名称，支持文字。例如 location=北京"),
    adm: str = Field(
        default="", description="城市的上级行政区划，可设定只在某个行政区划范围内进行搜索，用于排除重名城市或对结果进行过滤。例如 adm=beijing"),
    range: str = Field(
        default="cn", description="搜索范围，可设定只在某个国家或地区范围内进行搜索，国家和地区名称需使用ISO 3166 所定义的国家代码。如果不设置此参数，搜索范围将在所有城市。例如 range=cn"),
    number: int = Field(
        default=1, ge=1, le=20, description="返回结果的数量，取值范围1-20，默认返回 1 个结果。"),
    lang: str = Field(
        default="zh", description="多语言设置，支持 zh（中文）、en（英文）等")
) -> CitySearchResponse:
    """
    搜索城市信息
    @return:
        - CitySearchResponse: 城市搜索结果, 包含城市列表, 每个城市包含名称、ID、纬度、经度、二级行政区、一级行政区、国家、时区、UTC偏移、是否夏令时、类型、排名、和风天气链接。
    """
    params = {
        "location": location,
        "adm": adm,
        "range": range,
        "number": number,
        "lang": lang
    }

    try:
        data = await make_request("/geo/v2/city/lookup", params)
        city_search_response = CitySearchResponse.model_validate(data)
        return ToolResult(structured_content=city_search_response, content=format_cities(city_search_response.location))
    except Exception:
        raise


@mcp.tool(name="get_current_weather")
async def get_current_weather(
    location: str = Field(...,
                          description="位置信息，必须是 LocationID（如：101010100）或经纬度坐标（如：116.41,39.92）。如果只有城市名称，请先使用 search_city 工具获取 LocationID。"),
    lang: str = Field(default="zh", description="多语言设置，支持 zh（中文）、en（英文）等"),
    unit: str = Field(default="m", description="单位设置，m（公制）或 i（英制）")
) -> WeatherNowResponse:
    """
    获取实时天气信息

    注意：location 参数必须是有效的 LocationID 或经纬度坐标，不能直接使用城市名称。
    如果只有城市名称，请先使用 search_city 工具获取对应的 LocationID。

    @return:
        - WeatherNowResponse: 实时天气响应数据, 包含实时天气数据（观测时间、温度、体感温度、天气图标代码、天气状况文字描述、风向360度、风向、风力等级、风速、相对湿度、降水量、大气压强、能见度、云量、露点温度）、API更新时间、和风天气链接。
    """
    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

    try:
        data = await make_request("/v7/weather/now", params)
        weather_now_response = WeatherNowResponse.model_validate(data)
        return ToolResult(structured_content=weather_now_response, content=format_current_weather(weather_now_response.now))
    except Exception:
        raise


@mcp.tool(name="get_weather_hourly_forecast")
async def get_weather_hourly_forecast(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    hours: Literal["24h", "72h", "168h"] = Field(
        default="24h", description="预报小时数，可选值：24h（24小时预报）、72h（72小时预报）、168h（168小时预报）"),
    lang: str = Field(default="zh", description="多语言设置"),
    unit: str = Field(default="m", description="单位设置（m=公制，i=英制）")
) -> WeatherHourlyResponse:
    """
    逐小时天气预报API，提供全球城市24-168小时范围内逐小时天气预报，包括：温度、天气状况、风力、风速、风向、相对湿度、大气压强、降水概率、露点温度、云量。

    @return:
        - WeatherHourlyResponse: 逐小时天气预报响应数据, 包含逐小时天气预报列表、API更新时间、和风天气链接。
    """
    # 验证 hours 参数（虽然 Literal 类型已经限制，但显式验证可以提供更明确的错误信息）
    valid_hours = ["24h", "72h", "168h"]
    if hours not in valid_hours:
        raise ValueError(f"无效的预报小时数参数，支持: {', '.join(valid_hours)}")

    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }
    try:
        data = await make_request(f"/v7/weather/{hours}", params)
        weather_hourly_response = WeatherHourlyResponse.model_validate(data)
        return ToolResult(structured_content=weather_hourly_response, content=format_weather_hourly_forecast(weather_hourly_response.hourly))
    except Exception:
        raise


@mcp.tool(name="get_weather_daily_forecast")
async def get_weather_daily_forecast(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    days: Literal["3d", "7d", "10d", "15d", "30d"] = Field(
        default="3d", description="预报天数，支持 3d、7d、10d、15d、30d"),
    lang: str = Field(default="zh", description="多语言设置"),
    unit: str = Field(default="m", description="单位设置（m=公制，i=英制）")
) -> WeatherDailyResponse:
    """
    获取未来几天（3d、7d、10d、15d、30d）范围内的天气预报信息

    @return:
        - WeatherDailyResponse: 天气预报响应数据, 包含天气预报列表（每个预报包含日期、日出时间、日落时间、月出时间、月落时间、月相、月相图标、最高温度、最低温度、白天天气图标、白天天气状况、夜间天气图标、夜间天气状况、白天风向360度、白天风向、白天风力等级、白天风速、夜间风向360度、夜间风向、夜间风力等级、夜间风速、降水量、紫外线指数、相对湿度、大气压强、能见度、云量）、API更新时间、和风天气链接。
    """
    valid_days = ["3d", "7d", "10d", "15d", "30d"]
    if days not in valid_days:
        raise ValueError(f"无效的预报天数参数，支持: {', '.join(valid_days)}")

    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

    try:
        data = await make_request(f"/v7/weather/{days}", params)
        weather_daily_response = WeatherDailyResponse.model_validate(data)
        return ToolResult(structured_content=weather_daily_response, content=format_weather_daily_forecast(weather_daily_response.daily))

    except Exception:
        raise


@mcp.tool(name="get_weather_alerts")
async def get_weather_alerts(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    lang: str = Field(default="zh", description="多语言设置")
) -> WeatherAlertResponse:
    """
    获取天气预警信息

    @return:
        - WeatherAlertResponse: 天气预警响应数据, 包含天气预警列表（每个预警包含ID、发布机构、发布时间、标题、开始时间、结束时间、状态、等级、严重程度、严重程度颜色、类型代码、类型名称、紧急程度、确定性、预警内容、相关信息）、API更新时间、和风天气链接。
    """
    params = {
        "location": location,
        "lang": lang
    }

    try:
        data = await make_request("/v7/warning/now", params)
        weather_alert_response = WeatherAlertResponse.model_validate(data)
        return ToolResult(structured_content=weather_alert_response, content=format_weather_alerts(weather_alert_response.warning))
    except Exception:
        raise


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
    parser.add_argument("--transport", choices=["http", "stdio"], default="http",
                        help="传输方式：http 或 stdio")
    parser.add_argument("--port", type=int, default=8001,
                        help="HTTP 模式下的端口号")

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio 模式：通过标准输入输出与客户端通信
        mcp.run(transport="stdio")
    else:
        # HTTP 模式：启动 HTTP 服务器
        mcp.run(transport="http", port=args.port)

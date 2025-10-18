"""
和风天气 MCP Server
基于和风天气 API 提供天气查询服务
"""

import httpx
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field

try:
    from .config import config
except ImportError:
    from config import config

# 创建 MCP 实例
mcp = FastMCP("weather-mcp")


class WeatherNow(BaseModel):
    obsTime: str = Field(..., description="观测时间")
    temp: str = Field(..., description="温度")
    feelsLike: str = Field(..., description="体感温度")
    icon: str = Field(..., description="天气图标代码")
    text: str = Field(..., description="天气状况文字描述")
    wind360: str = Field(..., description="风向360度")
    windDir: str = Field(..., description="风向")
    windScale: str = Field(..., description="风力等级")
    windSpeed: str = Field(..., description="风速")
    humidity: str = Field(..., description="相对湿度")
    precip: str = Field(..., description="降水量")
    pressure: str = Field(..., description="大气压强")
    vis: str = Field(..., description="能见度")
    cloud: str = Field(..., description="云量")
    dew: str = Field(..., description="露点温度")


class WeatherDaily(BaseModel):
    fxDate: str = Field(..., description="预报日期")
    sunrise: str = Field(..., description="日出时间")
    sunset: str = Field(..., description="日落时间")
    moonrise: str = Field(..., description="月出时间")
    moonset: str = Field(..., description="月落时间")
    moonPhase: str = Field(..., description="月相")
    moonPhaseIcon: str = Field(..., description="月相图标")
    tempMax: str = Field(..., description="最高温度")
    tempMin: str = Field(..., description="最低温度")
    iconDay: str = Field(..., description="白天天气图标")
    textDay: str = Field(..., description="白天天气状况")
    iconNight: str = Field(..., description="夜间天气图标")
    textNight: str = Field(..., description="夜间天气状况")
    wind360Day: str = Field(..., description="白天风向360度")
    windDirDay: str = Field(..., description="白天风向")
    windScaleDay: str = Field(..., description="白天风力等级")
    windSpeedDay: str = Field(..., description="白天风速")
    wind360Night: str = Field(..., description="夜间风向360度")
    windDirNight: str = Field(..., description="夜间风向")
    windScaleNight: str = Field(..., description="夜间风力等级")
    windSpeedNight: str = Field(..., description="夜间风速")
    precip: str = Field(..., description="降水量")
    uvIndex: str = Field(..., description="紫外线指数")
    humidity: str = Field(..., description="相对湿度")
    pressure: str = Field(..., description="大气压强")
    vis: str = Field(..., description="能见度")
    cloud: str = Field(..., description="云量")


class WeatherResponse(BaseModel):
    code: str = Field(..., description="状态码")
    updateTime: str = Field(..., description="API 更新时间")
    fxLink: str = Field(..., description="和风天气链接")
    now: Optional[WeatherNow] = Field(None, description="实时天气数据")
    daily: Optional[List[WeatherDaily]] = Field(None, description="天气预报数据")
    refer: Dict[str, Any] = Field(..., description="数据来源信息")


async def make_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """发送 HTTP 请求到和风天气 API"""
    url = f"{config.QWEATHER_BASE_URL}{endpoint}"
    params["key"] = config.QWEATHER_API_KEY

    async with httpx.AsyncClient(timeout=config.QWEATHER_TIMEOUT) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"请求处理失败: {e}")


@mcp.tool(name="search_city")
async def search_city(
    location: str = Field(..., description="需要查询地区的名称，支持文字、以英文逗号分隔的经度,纬度坐标（十进制，最多支持小数点后两位）、LocationID或Adcode（仅限中国城市）。例如 location=北京 或 location=116.41,39.92"),
    adm: Optional[str] = Field(
        default="", description="城市的上级行政区划，可设定只在某个行政区划范围内进行搜索，用于排除重名城市或对结果进行过滤。例如 adm=beijing"),
    range: Optional[str] = Field(
        default="cn", description="搜索范围，可设定只在某个国家或地区范围内进行搜索，国家和地区名称需使用ISO 3166 所定义的国家代码。如果不设置此参数，搜索范围将在所有城市。例如 range=cn"),
    number: Optional[int] = Field(
        default=3, description="返回结果的数量，取值范围1-20，默认返回3个结果。"),
    lang: Optional[str] = Field(
        default="zh", description="多语言设置，支持 zh（中文）、en（英文）等")
) -> Dict[str, Any]:
    """
    搜索城市信息
    """
    if not config.QWEATHER_API_KEY:
        return {"error": "请设置 QWEATHER_API_KEY 环境变量"}

    params = {
        "location": location,
        "adm": adm,
        "range": range,
        "number": number,
        "lang": lang
    }

    try:
        data = await make_request("/geo/v2/city/lookup", params)
        return data
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(name="get_current_weather")
async def get_current_weather(
    location: str = Field(...,
                          description="位置信息，可以是 LocationID（如：101010100）或经纬度坐标（如：116.41,39.92）"),
    lang: str = Field(default="zh", description="多语言设置，支持 zh（中文）、en（英文）等"),
    unit: str = Field(default="m", description="单位设置，m（公制）或 i（英制）")
) -> Dict[str, Any]:
    """
    获取实时天气信息
    """
    if not config.QWEATHER_API_KEY:
        return {"error": "请设置 QWEATHER_API_KEY 环境变量"}

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


@mcp.tool(name="get_weather_forecast")
async def get_weather_forecast(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    days: str = Field(default="7d", description="预报天数，支持 3d、7d、10d、15d、30d"),
    lang: str = Field(default="zh", description="多语言设置"),
    unit: str = Field(default="m", description="单位设置（m=公制，i=英制）")
) -> Dict[str, Any]:
    """
    获取天气预报信息
    """
    if not config.QWEATHER_API_KEY:
        return {"error": "请设置 QWEATHER_API_KEY 环境变量"}

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


@mcp.tool(name="get_weather_alerts")
async def get_weather_alerts(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    lang: str = Field(default="zh", description="多语言设置")
) -> Dict[str, Any]:
    """
    获取天气预警信息
    """
    if not config.QWEATHER_API_KEY:
        return {"error": "请设置 QWEATHER_API_KEY 环境变量"}

    params = {
        "location": location,
        "lang": lang
    }

    try:
        data = await make_request("/v7/warning/now", params)
        return data
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(name="get_air_quality")
async def get_air_quality(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    lang: str = Field(default="zh", description="多语言设置")
) -> Dict[str, Any]:
    """
    获取空气质量信息
    """
    if not config.QWEATHER_API_KEY:
        return {"error": "请设置 QWEATHER_API_KEY 环境变量"}

    params = {
        "location": location,
        "lang": lang
    }

    try:
        data = await make_request("/v7/air/now", params)
        return data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    with open('./log.txt', 'a') as f:
        f.write("Starting weather server in  mode...\n")

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

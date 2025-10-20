"""
和风天气 MCP Server
基于和风天气 API 提供天气查询服务
文档地址: https://dev.qweather.com/docs/start/
"""

import asyncio
import httpx
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from pydantic import Field

try:
    # 尝试相对导入（当作为模块运行时）
    from .config import config
    from .models import CitySearchResponse, WeatherNowResponse, WeatherNow, City, WeatherDaily, WeatherDailyResponse, WeatherAlertResponse, WeatherAlert
except ImportError:
    # 绝对导入（当直接运行时）
    from config import config
    from models import CitySearchResponse, WeatherNowResponse, WeatherNow, City, WeatherDaily, WeatherDailyResponse, WeatherAlertResponse, WeatherAlert

# 创建 MCP 实例
mcp = FastMCP("weather-mcp")


async def make_request(endpoint: str, params: Dict[str, Any]) -> dict[str, Any]:
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


def format_city_search_results(data: Dict[str, Any]) -> str:
    """格式化城市搜索结果"""
    if "error" in data:
        return f"❌ 搜索失败: {data['error']}"

    if data.get("code") != "200":
        return f"❌ API 错误: {data.get('message', '未知错误')}"

    locations = data.get("location", [])
    if not locations:
        return "❌ 未找到匹配的城市"

    result = "🏙️ 城市搜索结果:\n"
    for i, location in enumerate(locations, 1):
        result += f"\n[{i}] {location.get('name', 'N/A')}\n"
        result += f"   📍 位置ID: {location.get('id', 'N/A')}\n"
        result += f"   🌍 国家: {location.get('country', 'N/A')}\n"
        result += f"   🏛️ 行政区: {location.get('adm1', 'N/A')}\n"
        result += f"   🏘️ 城市: {location.get('adm2', 'N/A')}\n"
        result += f"   📊 纬度: {location.get('lat', 'N/A')}\n"
        result += f"   📊 经度: {location.get('lon', 'N/A')}\n"
        result += f"   🕐 时区: {location.get('tz', 'N/A')}\n"
        result += f"   🌅 时区偏移: {location.get('utcOffset', 'N/A')}\n"
        result += f"   🌍 时区ID: {location.get('tz', 'N/A')}\n"
        result += f"   📍 类型: {location.get('type', 'N/A')}\n"
        result += f"   🔗 等级: {location.get('rank', 'N/A')}\n"
        result += f"   🌐 FX链接: {location.get('fxLink', 'N/A')}\n"

    return result


def format_current_weather(data: Dict[str, Any]) -> str:
    """格式化实时天气信息"""
    if "error" in data:
        return f"❌ 获取天气失败: {data['error']}"

    if data.get("code") != "200":
        return f"❌ API 错误: {data.get('message', '未知错误')}"

    now = data.get("now", {})
    if not now:
        return "❌ 未获取到天气数据"

    result = "🌤️ 实时天气信息:\n"
    result += f"📍 位置: {data.get('fxLink', 'N/A')}\n"
    result += f"🕐 更新时间: {data.get('updateTime', 'N/A')}\n\n"

    result += f"🌡️ 温度: {now.get('temp', 'N/A')}°C\n"
    result += f"🤔 体感温度: {now.get('feelsLike', 'N/A')}°C\n"
    result += f"☁️ 天气: {now.get('text', 'N/A')}\n"
    result += f"💨 风向: {now.get('windDir', 'N/A')} ({now.get('wind360', 'N/A')}°)\n"
    result += f"💨 风力: {now.get('windScale', 'N/A')}级\n"
    result += f"💨 风速: {now.get('windSpeed', 'N/A')} km/h\n"
    result += f"💧 湿度: {now.get('humidity', 'N/A')}%\n"
    result += f"🌧️ 降水量: {now.get('precip', 'N/A')} mm\n"
    result += f"📊 气压: {now.get('pressure', 'N/A')} hPa\n"
    result += f"👁️ 能见度: {now.get('vis', 'N/A')} km\n"
    result += f"☁️ 云量: {now.get('cloud', 'N/A')}%\n"
    result += f"🌡️ 露点: {now.get('dew', 'N/A')}°C\n"
    result += f"🕐 观测时间: {now.get('obsTime', 'N/A')}\n"

    return result


def format_weather_forecast(data: Dict[str, Any]) -> str:
    """格式化天气预报信息"""
    if "error" in data:
        return f"❌ 获取预报失败: {data['error']}"

    if data.get("code") != "200":
        return f"❌ API 错误: {data.get('message', '未知错误')}"

    daily = data.get("daily", [])
    if not daily:
        return "❌ 未获取到预报数据"

    result = "📅 天气预报:\n"
    result += f"📍 位置: {data.get('fxLink', 'N/A')}\n"
    result += f"🕐 更新时间: {data.get('updateTime', 'N/A')}\n\n"

    for i, day in enumerate(daily, 1):
        result += f"📅 第{i}天 ({day.get('fxDate', 'N/A')}):\n"
        result += f"   🌅 日出: {day.get('sunrise', 'N/A')}\n"
        result += f"   🌇 日落: {day.get('sunset', 'N/A')}\n"
        result += f"   🌙 月出: {day.get('moonrise', 'N/A')}\n"
        result += f"   🌙 月落: {day.get('moonset', 'N/A')}\n"
        result += f"   🌙 月相: {day.get('moonPhase', 'N/A')}\n"
        result += f"   🌡️ 温度: {day.get('tempMin', 'N/A')}°C ~ {day.get('tempMax', 'N/A')}°C\n"
        result += f"   ☀️ 白天: {day.get('textDay', 'N/A')}\n"
        result += f"   🌙 夜间: {day.get('textNight', 'N/A')}\n"
        result += f"   💨 白天风向: {day.get('windDirDay', 'N/A')} {day.get('windScaleDay', 'N/A')}级\n"
        result += f"   💨 夜间风向: {day.get('windDirNight', 'N/A')} {day.get('windScaleNight', 'N/A')}级\n"
        result += f"   🌧️ 降水量: {day.get('precip', 'N/A')} mm\n"
        result += f"   ☀️ 紫外线: {day.get('uvIndex', 'N/A')}\n"
        result += f"   💧 湿度: {day.get('humidity', 'N/A')}%\n"
        result += f"   📊 气压: {day.get('pressure', 'N/A')} hPa\n"
        result += f"   👁️ 能见度: {day.get('vis', 'N/A')} km\n"
        result += f"   ☁️ 云量: {day.get('cloud', 'N/A')}%\n\n"

    return result


def format_weather_alerts(data: Dict[str, Any]) -> str:
    """格式化天气预警信息"""
    if "error" in data:
        return f"❌ 获取预警失败: {data['error']}"

    if data.get("code") != "200":
        return f"❌ API 错误: {data.get('message', '未知错误')}"

    warnings = data.get("warning", [])
    if not warnings:
        return "✅ 当前无天气预警信息"

    result = "⚠️ 天气预警信息:\n"
    result += f"📍 位置: {data.get('fxLink', 'N/A')}\n"
    result += f"🕐 更新时间: {data.get('updateTime', 'N/A')}\n\n"

    for i, warning in enumerate(warnings, 1):
        result += f"⚠️ 预警 {i}:\n"
        result += f"   📋 标题: {warning.get('title', 'N/A')}\n"
        result += f"   📝 状态: {warning.get('status', 'N/A')}\n"
        result += f"   📊 等级: {warning.get('level', 'N/A')}\n"
        result += f"   📅 类型: {warning.get('type', 'N/A')}\n"
        result += f"   📅 类型名称: {warning.get('typeName', 'N/A')}\n"
        result += f"   📅 发布时间: {warning.get('pubTime', 'N/A')}\n"
        result += f"   📅 开始时间: {warning.get('startTime', 'N/A')}\n"
        result += f"   📅 结束时间: {warning.get('endTime', 'N/A')}\n"
        result += f"   📝 文本: {warning.get('text', 'N/A')}\n"
        result += f"   📝 相关: {warning.get('related', 'N/A')}\n\n"

    return result


def format_air_quality(data: Dict[str, Any]) -> str:
    """格式化空气质量信息"""
    if "error" in data:
        return f"❌ 获取空气质量失败: {data['error']}"

    if data.get("code") != "200":
        return f"❌ API 错误: {data.get('message', '未知错误')}"

    now = data.get("now", {})
    if not now:
        return "❌ 未获取到空气质量数据"

    result = "🌬️ 空气质量信息:\n"
    result += f"📍 位置: {data.get('fxLink', 'N/A')}\n"
    result += f"🕐 更新时间: {data.get('updateTime', 'N/A')}\n\n"

    result += f"📊 AQI: {now.get('aqi', 'N/A')}\n"
    result += f"📊 等级: {now.get('level', 'N/A')}\n"
    result += f"📊 类别: {now.get('category', 'N/A')}\n"
    result += f"🔴 主要污染物: {now.get('primary', 'N/A')}\n"
    result += f"📊 PM10: {now.get('pm10', 'N/A')} μg/m³\n"
    result += f"📊 PM2.5: {now.get('pm2p5', 'N/A')} μg/m³\n"
    result += f"📊 NO2: {now.get('no2', 'N/A')} μg/m³\n"
    result += f"📊 SO2: {now.get('so2', 'N/A')} μg/m³\n"
    result += f"📊 CO: {now.get('co', 'N/A')} mg/m³\n"
    result += f"📊 O3: {now.get('o3', 'N/A')} μg/m³\n"
    result += f"🕐 观测时间: {now.get('obsTime', 'N/A')}\n"

    return result


@mcp.tool(name="search_city")
async def search_city(
    location: str = Field(...,
                          description="需要查询地区的名称，支持文字。例如 location=北京"),
    adm: Optional[str] = Field(
        default="", description="城市的上级行政区划，可设定只在某个行政区划范围内进行搜索，用于排除重名城市或对结果进行过滤。例如 adm=beijing"),
    range: Optional[str] = Field(
        default="cn", description="搜索范围，可设定只在某个国家或地区范围内进行搜索，国家和地区名称需使用ISO 3166 所定义的国家代码。如果不设置此参数，搜索范围将在所有城市。例如 range=cn"),
    number: Optional[int] = Field(
        default=1, description="返回结果的数量，取值范围1-20，默认返回 1 个结果。"),
    lang: Optional[str] = Field(
        default="zh", description="多语言设置，支持 zh（中文）、en（英文）等")
) -> List[City]:
    """
    搜索城市信息
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
        return city_search_response.location
    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"


@mcp.tool(name="get_current_weather")
async def get_current_weather(
    location: str = Field(...,
                          description="位置信息，可以是 LocationID（如：101010100）或经纬度坐标（如：116.41,39.92）"),
    lang: str = Field(default="zh", description="多语言设置，支持 zh（中文）、en（英文）等"),
    unit: str = Field(default="m", description="单位设置，m（公制）或 i（英制）")
) -> WeatherNow:
    """
    获取实时天气信息
    """
    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

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
    unit: str = Field(default="m", description="单位设置（m=公制，i=英制）")
) -> List[WeatherDaily]:
    """
    获取天气预报信息
    """
    # 验证天数参数
    valid_days = ["3d", "7d", "10d", "15d", "30d"]
    if days not in valid_days:
        return f"❌ 无效的天数参数，支持: {', '.join(valid_days)}"

    params = {
        "location": location,
        "lang": lang,
        "unit": unit
    }

    try:
        data = await make_request(f"/v7/weather/{days}", params)
        weather_daily_response = WeatherDailyResponse.model_validate(data)
        return weather_daily_response.daily
    except Exception as e:
        return f"❌ 获取预报失败: {str(e)}"


@mcp.tool(name="get_weather_alerts")
async def get_weather_alerts(
    location: str = Field(..., description="位置信息，可以是 LocationID 或经纬度坐标"),
    lang: str = Field(default="zh", description="多语言设置")
) -> List[WeatherAlert]:
    """
    获取天气预警信息
    """
    params = {
        "location": location,
        "lang": lang
    }

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
    asyncio.run(main())
    # import argparse

    # parser = argparse.ArgumentParser(description="和风天气 MCP Server")
    # parser.add_argument("--transport", choices=["http", "stdio"], default="http",
    #                     help="传输方式：http 或 stdio")
    # parser.add_argument("--port", type=int, default=8001,
    #                     help="HTTP 模式下的端口号")

    # args = parser.parse_args()

    # if args.transport == "stdio":
    #     # Stdio 模式：通过标准输入输出与客户端通信
    #     mcp.run(transport="stdio")
    # else:
    #     # HTTP 模式：启动 HTTP 服务器
    #     mcp.run(transport="http", port=args.port)

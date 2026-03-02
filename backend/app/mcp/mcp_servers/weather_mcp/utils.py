from typing import Any, cast

import httpx
from jinja2 import Template

from .config import config
from .models import City, WeatherAlert, WeatherDaily, WeatherHourly, WeatherNow

city_template = Template(
    """
城市名称：{{ city.name }}
城市ID：{{ city.id }}
纬度：{{ city.lat }}
经度：{{ city.lon }}
二级行政区：{{ city.adm2 }}
一级行政区：{{ city.adm1 }}
国家：{{ city.country }}
时区：{{ city.tz }}
UTC偏移：{{ city.utcOffset }}
是否夏令时：{{ city.isDst }}
类型：{{ city.type }}
排名：{{ city.rank }}
和风天气链接：{{ city.fxLink }}
""".strip()
)


now_template = Template(
    """
观测时间：{{ now.obsTime }}
温度：{{ now.temp }}℃
体感温度：{{ now.feelsLike }}℃
天气图标代码：{{ now.icon }}
天气状况文字描述：{{ now.text }}
风向360度：{{ now.wind360 }}
风向：{{ now.windDir }}
风力等级：{{ now.windScale }}
风速：{{ now.windSpeed }}
相对湿度：{{ now.humidity }}
降水量：{{ now.precip }}
大气压强：{{ now.pressure }}
能见度：{{ now.vis }}
云量：{{ now.cloud }}
露点温度：{{ now.dew }}
""".strip()
)


daily_template = Template(
    """
预报日期：{{ daily.fxDate }}
日出时间：{{ daily.sunrise }}
日落时间：{{ daily.sunset }}
月出时间：{{ daily.moonrise }}
月落时间：{{ daily.moonset }}
月相：{{ daily.moonPhase }}
月相图标：{{ daily.moonPhaseIcon }}
最高温度：{{ daily.tempMax }}℃
最低温度：{{ daily.tempMin }}℃
白天天气图标：{{ daily.iconDay }}
白天天气状况：{{ daily.textDay }}
夜间天气图标：{{ daily.iconNight }}
夜间天气状况：{{ daily.textNight }}
""".strip()
)

alert_template = Template(
    """
预警ID：{{ alert.id }}
发布机构：{{ alert.sender }}
发布时间：{{ alert.pubTime }}
预警标题：{{ alert.title }}
开始时间：{{ alert.startTime }}
结束时间：{{ alert.endTime }}
状态：{{ alert.status }}
等级：{{ alert.level }}
严重程度：{{ alert.severity }}
严重程度颜色：{{ alert.severityColor }}
类型代码：{{ alert.type }}
类型名称：{{ alert.typeName }}
紧急程度：{{ alert.urgency }}
确定性：{{ alert.certainty }}
预警内容：{{ alert.text }}
相关信息：{{ alert.related }}
""".strip()
)


async def make_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """发送 HTTP 请求到和风天气 API"""
    url = f"{config.qweather_base_url}{endpoint}"
    params["key"] = config.qweather_api_key

    async with httpx.AsyncClient(timeout=config.qweather_timeout) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "200":
                error_code = data.get("code", "未知")
                error_msg = data.get("message", "未知错误")
                # 如果是 location 相关的错误，提供更友好的提示
                if error_code in ["400", "204"] or "location" in error_msg.lower():
                    raise ValueError(
                        f"位置参数无效 (错误代码: {error_code})。"
                        f"请使用 search_city 工具先获取有效的 LocationID，"
                        f"或使用经纬度坐标格式（如：116.41,39.92）。"
                        f"原始错误: {error_msg}"
                    )
                raise Exception(f"API 错误 (代码: {error_code}): {error_msg}")
            return cast(dict[str, Any], data)
        except httpx.HTTPStatusError as e:
            # 尝试解析响应体中的错误信息
            try:
                error_data = e.response.json()
                error_code = error_data.get("code", str(e.response.status_code))
                error_msg = error_data.get("message", e.response.text)
                if e.response.status_code == 400:
                    if "location" in str(error_data).lower():
                        raise ValueError(
                            f"位置参数无效。"
                            f"请使用 search_city 工具先获取有效的 LocationID，"
                            f"或使用经纬度坐标格式（如：116.41,39.92）。"
                            f"原始错误: {error_msg}"
                        )
                raise Exception(
                    f"HTTP {e.response.status_code} 错误 (代码: {error_code}): {error_msg}"
                )
            except Exception:
                raise Exception(f"HTTP 请求失败: {e}")
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"请求处理失败: {e}")


def format_cities(cities: list[City]) -> str:
    """
    将城市响应格式化为人类可读的文本
    """
    separator = "\n" + "-" * 50 + "\n"
    return separator.join([city_template.render(city=city).strip() for city in cities])


def format_current_weather(now: WeatherNow) -> str:
    """
    将当前天气响应格式化为人类可读的文本
    """
    return now_template.render(now=now).strip()


hourly_template = Template(
    """
预报时间：{{ hour.fxTime }}
温度：{{ hour.temp }}℃
{% if hour.feelsLike %}体感温度：{{ hour.feelsLike }}℃
{% endif %}天气图标代码：{{ hour.icon }}
天气状况文字描述：{{ hour.text }}
风向360度：{{ hour.wind360 }}
风向：{{ hour.windDir }}
风力等级：{{ hour.windScale }}
风速：{{ hour.windSpeed }}
相对湿度：{{ hour.humidity }}
降水量：{{ hour.precip }}
大气压强：{{ hour.pressure }}
{% if hour.vis %}能见度：{{ hour.vis }}
{% endif %}云量：{{ hour.cloud }}
露点温度：{{ hour.dew }}
""".strip()
)


def format_weather_hourly_forecast(hourly: list[WeatherHourly]) -> str:
    """
    将逐小时天气预报响应格式化为人类可读的文本
    """
    separator = "\n" + "-" * 50 + "\n"
    return separator.join(
        [hourly_template.render(hour=hour).strip() for hour in hourly]
    )


def format_weather_daily_forecast(daily: list[WeatherDaily]) -> str:
    """
    将逐日天气预报响应格式化为人类可读的文本
    """
    separator = "\n" + "-" * 50 + "\n"
    return separator.join(
        [daily_template.render(daily=daily).strip() for daily in daily]
    )


def format_weather_alerts(alerts: list[WeatherAlert]) -> str:
    """
    将天气预警响应格式化为人类可读的文本
    """
    separator = "\n" + "-" * 50 + "\n"
    return separator.join(
        [alert_template.render(alert=alert).strip() for alert in alerts]
    )

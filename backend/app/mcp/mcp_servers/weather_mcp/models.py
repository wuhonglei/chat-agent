"""
和风天气 API 数据模型定义
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class WeatherCommonResponse(BaseModel):
    code: str = Field(..., description="状态码")
    refer: Dict[str, Any] = Field(..., description="数据来源信息")


class City(BaseModel):
    name: str = Field(..., description="城市名称")
    id: str = Field(..., description="城市ID")
    lat: str = Field(..., description="纬度")
    lon: str = Field(..., description="经度")
    adm2: str = Field(..., description="二级行政区")
    adm1: str = Field(..., description="一级行政区")
    country: str = Field(..., description="国家")
    tz: str = Field(..., description="时区")
    utcOffset: str = Field(..., description="UTC偏移")
    isDst: str = Field(..., description="是否夏令时")
    type: str = Field(..., description="类型")
    rank: str = Field(..., description="排名")
    fxLink: str = Field(..., description="和风天气链接")


class CitySearchResponse(WeatherCommonResponse):
    location: list[City] = Field(..., description="城市列表")


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


class WeatherNowResponse(WeatherCommonResponse):
    now: WeatherNow = Field(..., description="实时天气数据")
    updateTime: str = Field(..., description="API更新时间")
    fxLink: str = Field(..., description="和风天气链接")


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


class WeatherDailyResponse(WeatherCommonResponse):
    daily: List[WeatherDaily] = Field(..., description="天气预报数据")
    updateTime: str = Field(..., description="API更新时间")
    fxLink: str = Field(..., description="和风天气链接")


class WeatherAlert(BaseModel):
    id: str = Field(..., description="预警ID")
    sender: str = Field(..., description="发布机构")
    pubTime: str = Field(..., description="发布时间")
    title: str = Field(..., description="预警标题")
    startTime: str = Field(..., description="开始时间")
    endTime: str = Field(..., description="结束时间")
    status: str = Field(..., description="状态")
    level: str = Field(..., description="等级")
    severity: str = Field(..., description="严重程度")
    severityColor: str = Field(..., description="严重程度颜色")
    type: str = Field(..., description="类型代码")
    typeName: str = Field(..., description="类型名称")
    urgency: str = Field(..., description="紧急程度")
    certainty: str = Field(..., description="确定性")
    text: str = Field(..., description="预警内容")
    related: str = Field(..., description="相关信息")


class WeatherAlertResponse(WeatherCommonResponse):
    warning: List[WeatherAlert] = Field(..., description="天气预警数据")
    updateTime: str = Field(..., description="API更新时间")
    fxLink: str = Field(..., description="和风天气链接")


class WeatherHourly(BaseModel):
    fxTime: str = Field(..., description="预报时间")
    temp: str = Field(..., description="温度")
    icon: str = Field(..., description="天气图标代码")
    text: str = Field(..., description="天气状况文字描述")
    wind360: str = Field(..., description="风向360度")
    windDir: str = Field(..., description="风向")
    windScale: str = Field(..., description="风力等级")
    windSpeed: str = Field(..., description="风速")
    humidity: str = Field(..., description="相对湿度")
    precip: str = Field(..., description="降水量")
    pressure: str = Field(..., description="大气压强")
    cloud: str = Field(..., description="云量")
    dew: str = Field(..., description="露点温度")
    # 可选字段，因为逐小时预报 API 可能不返回这些字段
    feelsLike: str | None = Field(default=None, description="体感温度")
    vis: str | None = Field(default=None, description="能见度")


class WeatherHourlyResponse(WeatherCommonResponse):
    hourly: List[WeatherHourly] = Field(..., description="逐小时天气预报数据")
    updateTime: str = Field(..., description="API更新时间")
    fxLink: str = Field(..., description="和风天气链接")

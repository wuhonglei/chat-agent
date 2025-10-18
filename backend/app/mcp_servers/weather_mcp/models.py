"""
和风天气 API 数据模型定义
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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

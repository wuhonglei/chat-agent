from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class IPLocatorResponse(BaseModel):
    """IP 地址定位响应模型"""
    query: str = Field(..., description="查询的 IP 地址")
    status: str = Field(..., description="请求状态，success 表示成功")
    country: str = Field(..., description="国家名称")
    countryCode: str = Field(..., description="国家代码（ISO 3166-1 alpha-2）")
    region: str = Field(..., description="地区代码")
    regionName: str = Field(..., description="地区名称")
    city: str = Field(..., description="城市名称")
    zip: Optional[str] = Field(None, description="邮政编码")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")
    timezone: str = Field(..., description="时区")
    isp: Optional[str] = Field(None, description="互联网服务提供商")
    org: Optional[str] = Field(None, description="组织名称")
    as_field: Optional[str] = Field(None, alias="as", description="AS 号码和名称")

    model_config = ConfigDict(populate_by_name=True, extra='allow')

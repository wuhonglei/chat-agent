"""
Tavily Search API 数据模型定义
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

# ================================ Search API ================================


class TavilySearchResultItem(BaseModel):
    """单个搜索结果"""
    title: str = Field(..., description="搜索结果的标题")
    url: str = Field(..., description="搜索结果的URL")
    content: str = Field(..., description="搜索结果的内容摘要")
    score: float = Field(..., description="搜索结果的相关性分数")
    raw_content: Optional[str] = Field(None, description="原始HTML内容")
    favicon: Optional[str] = Field(None, description="网站图标URL")


class TavilyImage(BaseModel):
    """搜索结果中的图片"""
    url: str = Field(..., description="图片URL")
    description: Optional[str] = Field(None, description="图片描述")


class TavilyAutoParameters(BaseModel):
    """自动参数配置"""
    topic: Optional[str] = Field(None, description="搜索主题类别")
    search_depth: Optional[str] = Field(None, description="搜索深度")
    time_range: Optional[str] = Field(None, description="时间范围")


class TavilySearchResponse(BaseModel):
    """Tavily搜索API响应"""
    query: str = Field(..., description="执行的搜索查询")
    answer: Optional[str] = Field(None, description="LLM生成的答案")
    images: List[TavilyImage] = Field(
        default_factory=list, description="相关图片列表")
    results: List[TavilySearchResultItem] = Field(..., description="搜索结果列表")
    response_time: float = Field(..., description="请求响应时间（秒）")
    auto_parameters: Optional[TavilyAutoParameters] = Field(
        None, description="自动参数配置")
    request_id: Optional[str] = Field(None, description="唯一请求标识符")


# ================================ Extract API ================================

class TavilyExtractResultItem(BaseModel):
    """单个提取结果"""
    url: str = Field(..., description="提取内容的URL")
    raw_content: str = Field(..., description="提取的原始内容")
    images: List[TavilyImage] = Field(
        default_factory=list, description="提取的图片列表")
    favicon: Optional[str] = Field(None, description="网站图标URL")


class TavilyFailedResultItem(BaseModel):
    """提取失败的URL结果"""
    url: str = Field(..., description="提取失败的URL")
    error: str = Field(..., description="错误信息")


class TavilyExtractResponse(BaseModel):
    """Tavily提取API响应"""
    results: List[TavilyExtractResultItem] = Field(
        ..., description="成功提取的内容列表")
    failed_results: List[TavilyFailedResultItem] = Field(
        default_factory=list, description="提取失败的URL列表")
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: Optional[str] = Field(None, description="唯一请求标识符")

# ================================ Crawl API ================================


class TavilyCrawlResultItem(BaseModel):
    """单个爬取结果"""
    url: str = Field(..., description="爬取内容的URL")
    raw_content: str = Field(..., description="爬取的原始内容")
    images: List[TavilyImage] = Field(
        default_factory=list, description="爬取的图片列表")
    favicon: Optional[str] = Field(None, description="网站图标URL")


class TavilyCrawlResponse(BaseModel):
    """Tavily爬取API响应"""
    base_url: str = Field(..., description="爬取的基础URL")
    results: List[TavilyCrawlResultItem] = Field(..., description="爬取结果列表")
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: Optional[str] = Field(None, description="唯一请求标识符")

# ================================ Map API ================================


class TavilyMapResponse(BaseModel):
    """Tavily地图API响应"""
    base_url: str = Field(..., description="映射的基础URL",
                          examples=["docs.tavily.com"])
    results: List[str] = Field(..., description="发现的URL列表", examples=[["https://docs.tavily.com/welcome",
                                                                       "https://docs.tavily.com/documentation/api-credits",
                                                                       "https://docs.tavily.com/documentation/about"
                                                                       ]])
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: Optional[str] = Field(None, description="唯一请求标识符")

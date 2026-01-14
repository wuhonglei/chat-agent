"""
Tavily Search API 数据模型定义
"""

from pydantic import BaseModel, Field

# ================================ Search API ================================


class TavilySearchResultItem(BaseModel):
    """单个搜索结果"""

    title: str | None = Field(None, description="搜索结果的标题")
    url: str | None = Field(None, description="搜索结果的URL")
    content: str | None = Field(None, description="搜索结果的内容摘要")
    score: float | None = Field(None, description="搜索结果的相关性分数")


class TavilyImage(BaseModel):
    """搜索结果中的图片"""

    url: str = Field(..., description="图片URL")
    description: str | None = Field(None, description="图片描述")


class TavilyAutoParameters(BaseModel):
    """自动参数配置"""

    topic: str | None = Field(None, description="搜索主题类别")
    search_depth: str | None = Field(None, description="搜索深度")
    time_range: str | None = Field(None, description="时间范围")


class TavilySearchResponse(BaseModel):
    """Tavily搜索API响应"""

    query: str | None = Field(None, description="执行的搜索查询")
    results: list[TavilySearchResultItem] = Field(..., description="搜索结果列表")
    response_time: float = Field(..., description="请求响应时间（秒）")
    auto_parameters: TavilyAutoParameters | None = Field(
        None, description="自动参数配置"
    )
    request_id: str | None = Field(None, description="唯一请求标识符")


# ================================ Extract API ================================


class TavilyExtractResultItem(BaseModel):
    """单个提取结果"""

    title: str | None = Field(default="", description="提取内容的标题")
    url: str | None = Field(default="", description="提取内容的URL")
    raw_content: str | None = Field(default="", description="提取的原始内容")


class TavilyFailedResultItem(BaseModel):
    """提取失败的URL结果"""

    url: str = Field(..., description="提取失败的URL")
    error: str = Field(..., description="错误信息")


class TavilyExtractResponse(BaseModel):
    """Tavily提取API响应"""

    results: list[TavilyExtractResultItem] = Field(
        ..., description="成功提取的内容列表"
    )
    failed_results: list[TavilyFailedResultItem] = Field(
        default_factory=list, description="提取失败的URL列表"
    )
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: str | None = Field(None, description="唯一请求标识符")


# ================================ Crawl API ================================


class TavilyCrawlResultItem(BaseModel):
    """单个爬取结果"""

    url: str = Field(..., description="爬取内容的URL")
    raw_content: str = Field(..., description="爬取的原始内容")
    images: list[TavilyImage] = Field(
        default_factory=list, description="爬取的图片列表"
    )
    favicon: str | None = Field(None, description="网站图标URL")


class TavilyCrawlResponse(BaseModel):
    """Tavily爬取API响应"""

    base_url: str = Field(..., description="爬取的基础URL")
    results: list[TavilyCrawlResultItem] = Field(..., description="爬取结果列表")
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: str | None = Field(None, description="唯一请求标识符")


# ================================ Map API ================================


class TavilyMapResponse(BaseModel):
    """Tavily地图API响应"""

    base_url: str = Field(
        ..., description="映射的基础URL", examples=["docs.tavily.com"]
    )
    results: list[str] = Field(
        ...,
        description="发现的URL列表",
        examples=[
            [
                "https://docs.tavily.com/welcome",
                "https://docs.tavily.com/documentation/api-credits",
                "https://docs.tavily.com/documentation/about",
            ]
        ],
    )
    response_time: float = Field(..., description="请求响应时间（秒）")
    request_id: str | None = Field(None, description="唯一请求标识符")

"""
Tavily Search MCP Server
Based on Tavily API for web search, content extraction, crawling and mapping
Documentation: https://docs.tavily.com/
"""

from typing import Literal

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field
from tavily import AsyncTavilyClient

# 需要在 tavily_mcp 目录的上层执行: uv run -m tavily_mcp.server
from .config import config
from .models import (
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilyMapResponse,
    TavilySearchResponse,
)
from .utils import (
    filter_search_results_by_score,
    format_crawl_results,
    format_extract_results,
    format_map_results,
    format_search_results,
)

# Create MCP instance and Tavily client
mcp = FastMCP(
    name="Tavily Search MCP Service",
)
client = AsyncTavilyClient(api_key=config.TAVILY_API_KEY)


@mcp.tool(name="web_search")
async def web_search(
    query: str = Field(..., description="要执行的搜索查询"),
    auto_parameters: bool = Field(
        default=True,
        description="启用后，Tavily 会根据查询内容与意图自动配置搜索参数。启用时每次请求消耗 2 个 API 额度。",
    ),
    topic: Literal["general", "news", "finance"] = Field(
        default="general",
        description="搜索类别：'general'、'news'、'finance'（默认 'general'）",
    ),
    search_depth: Literal["advanced", "basic", "fast", "ultra-fast"] = Field(
        default="advanced",
        description="搜索深度：'advanced'（相关性最佳）、'basic'（均衡）、'fast'（更低延迟）、'ultra-fast'（最低延迟）",
    ),
    chunks_per_source: int = Field(
        default=3,
        ge=1,
        le=5,
        description="每个来源返回的相关片段上限（1-5）。仅在 search_depth 为 'advanced' 或 'fast' 时可用",
    ),
    max_results: int = Field(
        default=5,
        ge=0,
        le=20,
        description="返回的搜索结果最大数量（0-20）",
    ),
    time_range: Literal[
        "day",
        "week",
        "month",
        "year",
        "d",
        "w",
        "m",
        "y",
    ]
    | None = Field(
        default=None,
        description="时间范围：'day'、'week'、'month'、'year' 或简写 'd'、'w'、'm'、'y'",
    ),
    start_date: str = Field(
        default=None,
        description="返回指定开始日期之后的结果。格式：YYYY-MM-DD",
    ),
    end_date: str = Field(
        default=None,
        description="返回指定结束日期之前的结果。格式：YYYY-MM-DD",
    ),
    include_domains: list[str] = Field(
        default=None,
        description="需要包含的域名列表（最多 300 个域名）",
    ),
    exclude_domains: list[str] = Field(
        default=None,
        description="需要排除的域名列表（最多 150 个域名）",
    ),
    country: str = Field(
        default=None,
        description="提升特定国家的搜索结果，仅当 topic 为 'general' 可用。国家名需为小写英文",
    ),
) -> TavilySearchResponse:
    """
    A powerful web search tool that provides comprehensive, real-time results using Tavily's AI search engine.
    Returns relevant web content with customizable parameters for result count, content type, and domain filtering.
    Ideal for gathering current information, news, and detailed web content analysis.
    """
    try:
        # Use AsyncTavilyClient.search method
        response = await client.search(
            query=query,
            auto_parameters=auto_parameters,
            topic=topic,
            search_depth=search_depth,
            chunks_per_source=chunks_per_source,
            max_results=max_results,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            country=country,
        )
        try:
            data = TavilySearchResponse.model_validate(response)
            data.is_chunked = search_depth in ["advanced", "fast"] and query is not None

            # 根据分数过滤搜索结果
            data.filtered_results, data.ignored_results = (
                filter_search_results_by_score(data.results)
            )

            return ToolResult(
                structured_content=data,
                content=format_search_results(data),
            )
        except Exception as e:
            raise ValueError(f"搜索响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


@mcp.tool(name="url_content_extract")
async def url_content_extract(
    urls: list[str] = Field(
        ..., description="要提取内容的 URL 列表（最多 100 个 URL）"
    ),
    query: str | None = Field(
        default=None,
        description="用于对提取内容片段重排的用户意图。提供后会按与该查询的相关性重排。",
    ),
    extract_depth: Literal["advanced", "basic"] = Field(
        default="advanced",
        description="提取深度：'advanced'（内容更丰富）、'basic'（更省额度）",
    ),
) -> TavilyExtractResponse:
    """
    A powerful web content extraction tool that retrieves and processes raw content from specified URLs,
    ideal for data collection, content analysis, and research tasks.
    """
    try:
        response = await client.extract(
            urls=urls,
            extract_depth=extract_depth,
            query=query,
        )
        try:
            data = TavilyExtractResponse.model_validate(response)
            data.is_chunked = extract_depth in ["advanced"] and query is not None
            return ToolResult(
                structured_content=data,
                content=format_extract_results(data),
            )
        except Exception as e:
            raise ValueError(f"提取响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


@mcp.tool(name="site_crawl_extract")
async def site_crawl_extract(
    url: str = Field(..., description="开始爬取的根 URL"),
    instructions: str | None = Field(
        default=None,
        description="爬虫的自然语言指令，用于指定应返回的页面类型",
    ),
    max_depth: int = Field(
        default=1,
        ge=1,
        le=3,
        description="最大爬取深度，定义从根 URL 可探索的深度（1-3）",
    ),
    max_breadth: int = Field(
        default=20,
        ge=1,
        le=50,
        description="每层最多跟随的链接数（1-50）",
    ),
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="爬虫处理的链接总数上限（1-200）",
    ),
    select_paths: list[str] = Field(
        default_factory=list,
        description="仅选择匹配路径的正则（如 /docs/.*, /api/v1.*）",
    ),
    select_domains: list[str] = Field(
        default_factory=list,
        description="限制爬取域名或子域名的正则（如 ^docs\\.example\\.com$）",
    ),
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="用于排除路径的正则",
    ),
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="用于排除域名或子域名的正则",
    ),
    allow_external: bool = Field(
        default=True,
        description="是否在最终结果中包含外部链接",
    ),
    extract_depth: Literal["basic", "advanced"] = Field(
        default="basic",
        description="提取深度：'basic'（更省额度）、'advanced'（内容更丰富）",
    ),
) -> TavilyCrawlResponse:
    """
    A powerful web crawler that initiates a structured web crawl starting from a specified base URL.
    The crawler expands from that point like a graph, following internal links across pages.
    You can control how deep and wide it goes, and guide it to focus on specific sections of the site.
    """
    try:
        response = await client.crawl(
            url=url,
            instructions=instructions,
            max_depth=max_depth,
            max_breadth=max_breadth,
            limit=limit,
            select_paths=select_paths,
            select_domains=select_domains,
            exclude_paths=exclude_paths,
            exclude_domains=exclude_domains,
            allow_external=allow_external,
            extract_depth=extract_depth,
        )
        try:
            data = TavilyCrawlResponse.model_validate(response)
            data.is_chunked = extract_depth in ["advanced"] and instructions is not None
            return ToolResult(
                structured_content=data, content=format_crawl_results(data)
            )
        except Exception as e:
            raise ValueError(f"爬取响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


# @mcp.tool(name="web_site_map")
async def web_site_map(
    url: str = Field(..., description="开始映射的根 URL"),
    instructions: str | None = Field(
        default=None,
        description="映射器自然语言指令。提供后费用从每 10 页 1 额度提高到 2 额度",
    ),
    max_depth: int = Field(
        default=1,
        ge=1,
        description="最大映射深度，定义从根 URL 可探索多远",
    ),
    max_breadth: int = Field(
        default=20,
        ge=1,
        description="每层（每页）最多跟随的链接数",
    ),
    limit: int = Field(
        default=50,
        ge=1,
        description="映射器处理的链接总数上限",
    ),
    select_paths: list[str] = Field(
        default_factory=list,
        description="仅选择匹配路径的正则（如 /docs/.*, /api/v1.*）",
    ),
    select_domains: list[str] = Field(
        default_factory=list,
        description="仅选择特定域名或子域名的正则（如 ^docs\\.example\\.com$）",
    ),
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="用于排除路径的正则（如 /private/.*, /admin/.*）",
    ),
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="用于排除域名或子域名的正则（如 ^private\\.example\\.com$）",
    ),
    allow_external: bool = Field(
        default=True,
        description="是否在结果列表中包含外部域名链接",
    ),
) -> TavilyMapResponse:
    """
    A powerful web mapping tool that creates a structured map of website URLs,
    allowing you to discover and analyze site structure, content organization, and navigation paths.
    Perfect for site audits, content discovery, and understanding website architecture.
    """
    try:
        response = await client.map(
            url=url,
            instructions=instructions,
            max_depth=max_depth,
            max_breadth=max_breadth,
            limit=limit,
            select_paths=select_paths if select_paths else None,
            select_domains=select_domains if select_domains else None,
            exclude_paths=exclude_paths if exclude_paths else None,
            exclude_domains=exclude_domains if exclude_domains else None,
            allow_external=allow_external,
        )
        try:
            data = TavilyMapResponse.model_validate(response)
            return ToolResult(structured_content=data, content=format_map_results(data))
        except Exception as e:
            raise ValueError(f"映射响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tavily MCP Server")
    parser.add_argument(
        "--transport",
        choices=["http", "stdio"],
        default="http",
        help="Transport mode: http or stdio",
    )
    parser.add_argument(
        "--port", type=int, default=8002, help="Port number for HTTP mode"
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio mode: communicate with client via stdin/stdout
        mcp.run(transport="stdio")
    else:
        # HTTP mode: start HTTP server
        mcp.run(transport="http", port=args.port)

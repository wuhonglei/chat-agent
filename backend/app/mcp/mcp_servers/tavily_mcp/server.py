"""
Tavily Search MCP Server
Based on Tavily API for web search, content extraction, crawling and mapping
Documentation: https://docs.tavily.com/
"""

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


@mcp.tool(name="tavily_search")
async def tavily_search(
    query: str = Field(..., description="The search query to execute with Tavily"),
    auto_parameters: bool = Field(
        default=True,
        description="When enabled, Tavily automatically configures search parameters based on your query's content and intent. Uses 2 API credits per request when enabled.",
    ),
    topic: str = Field(
        default="general",
        description="The category of the search. Options: 'general', 'news', 'finance'",
    ),
    search_depth: str = Field(
        default="advanced",
        description="The depth of the search. Options: 'advanced', 'basic', 'fast', 'ultra-fast'. advanced: Highest relevance with increased latency. Best for detailed, high-precision queries. Returns multiple semantically relevant snippets per URL (configurable via chunks_per_source). basic: A balanced option for relevance and latency. Ideal for general-purpose searches. Returns one NLP summary per URL. fast: Prioritizes lower latency while maintaining good relevance. Returns multiple semantically relevant snippets per URL (configurable via chunks_per_source). ultra-fast: Minimizes latency above all else. Best for time-critical use cases. Returns one NLP summary per URL.",
    ),
    chunks_per_source: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of relevant chunks returned per source (1-5). Available when search_depth is 'advanced' or 'fast'",
    ),
    max_results: int = Field(
        default=5,
        ge=0,
        le=20,
        description="The maximum number of search results to return (0-20)",
    ),
    time_range: str = Field(
        default=None,
        description="The time range back from the current date to filter results. Options: 'day', 'week', 'month', 'year', 'd', 'w', 'm', 'y'",
    ),
    start_date: str = Field(
        default=None,
        description="Will return all results after the specified start date. Format: YYYY-MM-DD",
    ),
    end_date: str = Field(
        default=None,
        description="Will return all results before the specified end date. Format: YYYY-MM-DD",
    ),
    include_domains: list[str] = Field(
        default=None,
        description="A list of domains to specifically include in the search results (max 300 domains)",
    ),
    exclude_domains: list[str] = Field(
        default=None,
        description="A list of domains to specifically exclude from the search results (max 150 domains)",
    ),
    country: str = Field(
        default=None,
        description="Boost search results from a specific country. Available only if topic is 'general'. Country names must be in lowercase, plain English",
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
            return ToolResult(
                structured_content=data, content=format_search_results(data)
            )
        except Exception as e:
            raise ValueError(f"搜索响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


@mcp.tool(name="tavily_extract")
async def tavily_extract(
    urls: list[str] = Field(..., description="要提取内容的URL（字符串或数组）"),
    query: str | None = Field(
        default=None, description="用户意图查询，用于重新排序提取的内容块"
    ),
    chunks_per_source: int = Field(
        default=3,
        ge=1,
        le=5,
        description="每个源返回的最大相关块数（1-5，默认3）, 仅当提供 query 时有效",
    ),
    extract_depth: str = Field(
        default="advanced",
        description="提取深度。'basic'为基本提取（每5个成功URL提取消耗1积分），'advanced'为高级提取（每5个成功URL提取消耗2积分），包含表格和嵌入内容。选项：'basic', 'advanced'",
    ),
    include_images: bool = Field(default=False, description="是否在响应中包含图片列表"),
    include_favicon: bool = Field(default=False, description="是否包含favicon URL"),
    format: str = Field(
        default="markdown",
        description="内容格式。'markdown'返回markdown格式，'text'返回纯文本格式（可能增加延迟）。选项：'markdown', 'text'",
    ),
) -> TavilyExtractResponse:
    """
    A powerful web content extraction tool that retrieves and processes raw content from specified URLs,
    ideal for data collection, content analysis, and research tasks.
    """
    try:
        # Use AsyncTavilyClient.extract method
        extract_params = {
            "urls": urls,
            "extract_depth": extract_depth,
            "include_images": include_images,
            "include_favicon": include_favicon,
            "format": format,
        }

        # 只有当query不为None时才添加
        if query is not None:
            extract_params["query"] = query

        # 只有当chunks_per_source不为默认值时才添加（让API使用默认值）
        if chunks_per_source != 3:
            extract_params["chunks_per_source"] = chunks_per_source

        response = await client.extract(**extract_params)
        try:
            data = TavilyExtractResponse.model_validate(response)
            return ToolResult(
                structured_content=data, content=format_extract_results(data)
            )
        except Exception as e:
            raise ValueError(f"提取响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


@mcp.tool(name="tavily_crawl")
async def tavily_crawl(
    url: str = Field(..., description="The root URL to begin the crawl"),
    instructions: str = Field(
        default=None,
        description="Natural language instructions for the crawler. Instructions specify which types of pages the crawler should return",
    ),
    max_depth: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Max depth of the crawl. Defines how far from the base URL the crawler can explore (1-3)",
    ),
    max_breadth: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Max number of links to follow per level of the tree (1-50)",
    ),
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Total number of links the crawler will process before stopping (1-200)",
    ),
    select_paths: list[str] = Field(
        default_factory=list,
        description="Regex patterns to select only URLs with specific path patterns (e.g., /docs/.*, /api/v1.*)",
    ),
    select_domains: list[str] = Field(
        default_factory=list,
        description="Regex patterns to restrict crawling to specific domains or subdomains (e.g., ^docs\\.example\\.com$)",
    ),
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="Regex patterns to exclude URLs with specific path patterns",
    ),
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Regex patterns to exclude specific domains or subdomains from crawling",
    ),
    allow_external: bool = Field(
        default=True,
        description="Whether to return external links in the final response",
    ),
    extract_depth: str = Field(
        default="basic",
        description="The depth of the extraction process. 'basic' costs 1 credit per 5 successful URL extractions, 'advanced' costs 2 credits per 5 successful URL extractions. Options: 'basic', 'advanced'",
    ),
    format: str = Field(
        default="markdown",
        description="The format of the extracted web page content. 'markdown' returns content in markdown format, 'text' returns plain text and may increase latency. Options: 'markdown', 'text'",
    ),
    include_favicon: bool = Field(
        default=False, description="Whether to include the favicon URL for each result"
    ),
) -> TavilyCrawlResponse:
    """
    A powerful web crawler that initiates a structured web crawl starting from a specified base URL.
    The crawler expands from that point like a graph, following internal links across pages.
    You can control how deep and wide it goes, and guide it to focus on specific sections of the site.
    """
    try:
        # Use AsyncTavilyClient.crawl method
        response = await client.crawl(
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
            extract_depth=extract_depth,
            format=format,
            include_favicon=include_favicon,
        )
        try:
            data = TavilyCrawlResponse.model_validate(response)
            return ToolResult(
                structured_content=data, content=format_crawl_results(data)
            )
        except Exception as e:
            raise ValueError(f"爬取响应验证失败: {str(e)}")
    except Exception:
        # 直接重新抛出原始异常，保持异常类型和堆栈跟踪
        raise


# @mcp.tool(name="tavily_map")
async def tavily_map(
    url: str = Field(..., description="The root URL to begin the mapping"),
    instructions: str = Field(
        default=None,
        description="Natural language instructions for the mapper. When specified, the cost increases to 2 API credits per 10 successful pages instead of 1 API credit per 10 pages",
    ),
    max_depth: int = Field(
        default=1,
        ge=1,
        description="Max depth of the mapping. Defines how far from the base URL the crawler can explore",
    ),
    max_breadth: int = Field(
        default=20,
        ge=1,
        description="Max number of links to follow per level of the tree (i.e., per page)",
    ),
    limit: int = Field(
        default=50,
        ge=1,
        description="Total number of links the crawler will process before stopping",
    ),
    select_paths: list[str] = Field(
        default_factory=list,
        description="Regex patterns to select only URLs with specific path patterns (e.g., /docs/.*, /api/v1.*)",
    ),
    select_domains: list[str] = Field(
        default_factory=list,
        description="Regex patterns to select crawling to specific domains or subdomains (e.g., ^docs\\.example\\.com$)",
    ),
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="Regex patterns to exclude URLs with specific path patterns (e.g., /private/.*, /admin/.*)",
    ),
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Regex patterns to exclude specific domains or subdomains from crawling (e.g., ^private\\.example\\.com$)",
    ),
    allow_external: bool = Field(
        default=True,
        description="Whether to include external domain links in the final results list",
    ),
) -> TavilyMapResponse:
    """
    A powerful web mapping tool that creates a structured map of website URLs,
    allowing you to discover and analyze site structure, content organization, and navigation paths.
    Perfect for site audits, content discovery, and understanding website architecture.
    """
    try:
        # Use AsyncTavilyClient.map method
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

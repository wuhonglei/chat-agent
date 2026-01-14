from .models import (
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilyMapResponse,
    TavilySearchResponse,
)


def format_results(response: TavilySearchResponse | TavilyExtractResponse) -> str:
    """
    将 Tavily API 响应格式化为人类可读的文本

    Args:
        response: TavilySearchResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    # Include answer if available
    if hasattr(response, "answer") and response.answer:
        output.append(f"答案: {response.answer}")

    # Format detailed search results
    output.append("Detailed Results:")
    for result in response.results:
        output.append(f"\n标题: {result.title}")
        output.append(f"URL 链接: {result.url}")
        if hasattr(result, "content") and result.content:
            output.append(f"搜索摘要: {result.content}")
        if hasattr(result, "raw_content") and result.raw_content:
            output.append(f"网页内容: {result.raw_content}")
        if hasattr(result, "favicon") and result.favicon:
            output.append(f"网站图标: {result.favicon}")

    # Add images section if available
    if hasattr(response, "images") and response.images and len(response.images) > 0:
        output.append("图片列表:")
        for index, image in enumerate(response.images, start=1):
            output.append(f"[{index}] 图片 URL: {image.url}")
            if image.description:
                output.append(f"图片描述: {image.description}")

    return "\n".join(output)


def format_crawl_results(response: TavilyCrawlResponse) -> str:
    """
    将 Tavily Crawl API 响应格式化为人类可读的文本

    Args:
        response: TavilyCrawlResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    output.append("Crawl Results:")
    output.append(f"Base URL: {response.base_url}")

    output.append("\nCrawled Pages:")
    for index, page in enumerate(response.results, start=1):
        output.append(f"\n[{index}] URL: {page.url}")
        if page.raw_content:
            # Truncate content if it's too long
            content_preview = (
                page.raw_content[:200] + "..."
                if len(page.raw_content) > 200
                else page.raw_content
            )
            output.append(f"Content: {content_preview}")
        if page.favicon:
            output.append(f"Favicon: {page.favicon}")

    return "\n".join(output)


def format_map_results(response: TavilyMapResponse) -> str:
    """
    将 Tavily Map API 响应格式化为人类可读的文本

    Args:
        response: TavilyMapResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    output.append("Site Map Results:")
    output.append(f"Base URL: {response.base_url}")

    output.append("\nMapped Pages:")
    for index, page in enumerate(response.results, start=1):
        output.append(f"\n[{index}] URL: {page}")

    return "\n".join(output)

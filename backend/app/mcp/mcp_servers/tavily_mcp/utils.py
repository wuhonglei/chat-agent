from .models import (
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilyMapResponse,
    TavilySearchResponse,
    TavilySearchResultItem,
)


def format_search_results(
    is_chunked: bool,
    response: TavilySearchResponse,
    ignored_results: list[TavilySearchResultItem],
) -> str:
    """
    将 Tavily Search API 响应格式化为人类可读的文本

    Args:
        response: TavilySearchResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    # Format detailed search results
    output.append("网页搜索结果 (Tavily Search API):")
    for index, result in enumerate(response.results, start=1):
        temp_output: list[str] = []
        temp_output.append(f"[{index}] 标题: {result.title}")
        temp_output.append(f"URL: {result.url}")
        if result.score:
            temp_output.append(f"相关性分数: {result.score}")
        if result.content:
            if is_chunked:
                chunks = result.content.split("[...]")
                for idx, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"[{idx}] 相关内容: {chunk}")
            else:
                temp_output.append(f"网页内容: {result.content}")
        output.append("\n".join(temp_output))

    if ignored_results:
        output.append("\n以下结果因相关性分数低于阈值 0.5 而被忽略（可作为补充信息）:")
        for index, result in enumerate(ignored_results, start=1):
            temp_output: list[str] = []
            temp_output.append(f"[{index}] 标题: {result.title}")
            temp_output.append(f"URL: {result.url}")
            if result.score:
                temp_output.append(f"相关性分数: {result.score}")
            output.append("\n".join(temp_output))

    return "\n".join(output)


def format_extract_results(is_chunked: bool, response: TavilyExtractResponse) -> str:
    """
    将 Tavily Extract API 响应格式化为人类可读的文本

    Args:
        response: TavilyExtractResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    # Format successful extraction results
    output.append("网页提取结果 (Tavily Extract API):")
    for index, result in enumerate(response.results, start=1):
        temp_output: list[str] = []
        temp_output.append(f"[{index}] 标题: {result.title}")
        temp_output.append(f"URL: {result.url}")
        if result.raw_content:
            if is_chunked:
                chunks = result.raw_content.split("[...]")
                for idx, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"[{idx}] 相关内容: {chunk}")
            else:
                temp_output.append(f"提取内容: {result.raw_content}")
        output.append("\n".join(temp_output))

    if response.failed_results:
        output.append("\n网页提取失败的URL:")
        for index, failed in enumerate(response.failed_results, start=1):
            temp_output: list[str] = []
            temp_output.append(f"[{index}] URL: {failed.url}")
            temp_output.append(f"错误: {failed.error}")
            output.append("\n".join(temp_output))

    return "\n".join(output)


def format_crawl_results(is_chunked: bool, response: TavilyCrawlResponse) -> str:
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
        temp_output: list[str] = []
        temp_output.append(f"[{index}] URL: {page.url}")
        if page.raw_content:
            if is_chunked:
                chunks = page.raw_content.split("[...]")
                for idx, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"[{idx}] 相关内容: {chunk}")
            else:
                temp_output.append(f"提取内容: {page.raw_content}")
        output.append("\n".join(temp_output))

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

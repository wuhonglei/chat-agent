import math
import re

from .models import (
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilyMapResponse,
    TavilySearchResponse,
    TavilySearchResultItem,
)


def clean_invisible_chars(
    raw_str: str, full_clean: bool = False, keep_edges: bool = False
) -> str:
    """
    清理字符串中的常见不可见 Unicode 字符（解决文本处理中的"隐形坑"）

    Args:
        raw_str: 待处理的原始字符串
        full_clean: 是否全量清理（True：移除所有不可打印字符；False：仅移除高频有害不可见字符，默认）
        keep_edges: 仅清理字符串首尾的不可见字符（True：仅首尾；False：全局清理，默认）

    Returns:
        清理后的干净字符串

    Raises:
        TypeError: 输入不是字符串类型时抛出
    """
    # 输入类型校验
    if not isinstance(raw_str, str):
        raise TypeError(
            f"输入必须是字符串类型，当前输入类型为 {type(raw_str).__name__}"
        )

    # 情况1：仅清理首尾不可见字符（先定义待清理的字符集合）
    invisible_char_set = {
        "\u200b",
        "\u200c",
        "\u200d",
        "\ufeff",
        "\u00a0",
        "\u202f",
        "\t",
        "\n",
        "\r",
        " ",
    }
    if keep_edges:
        edge_clean_chars = "".join(invisible_char_set)
        return raw_str.strip(edge_clean_chars)

    # 情况2：全局清理（分 普通清理 / 全量清理 两种粒度）
    if full_clean:
        # 全量清理：匹配所有 Unicode 不可打印字符（\p{C}），支持多语言环境
        # re.UNICODE 开启 Unicode 匹配支持，兼容 Python 3.7+
        full_clean_pattern = re.compile(r"\p{C}", flags=re.UNICODE)
        cleaned_str = full_clean_pattern.sub("", raw_str)
    else:
        # 普通清理（默认推荐）：仅移除高频有害不可见字符，保留正常排版（如换行、Tab 缩进）
        # 匹配：零宽度系列 + 不换行空格 + BOM 标记，不影响正常文本格式
        normal_clean_pattern = re.compile(r"[\u200b\u200c\u200d\ufeff\u00a0\u202f]")
        cleaned_str = normal_clean_pattern.sub("", raw_str)

    return cleaned_str


def format_query_search_results(response: TavilySearchResponse) -> str:
    """
    将 Tavily Search API 响应格式化为人类可读的文本

    Args:
        response: TavilySearchResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []
    query = response.query
    is_chunked = response.is_chunked
    filtered_results = response.filtered_results
    ignored_results = response.ignored_results

    # Format detailed search results
    if filtered_results:
        output.append(
            f"执行的搜索查询: {query}\n{len(filtered_results)} 个高相关性搜索结果如下:"
        )
    # 先输出高相关性结果
    for index, result in enumerate(filtered_results, start=1):
        temp_output: list[str] = [f"\n第 {index} 个搜索结果的详细信息如下:"]
        temp_output.append(f"标题: {clean_invisible_chars(result.title)}")
        temp_output.append(f"URL: {result.url}")
        if result.score:
            temp_output.append(f"相关性分数: {result.score:.2f}")
        content = clean_invisible_chars(result.content)
        if content:
            if is_chunked:
                chunks = content.split("[...]")
                for i, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"相关内容 {i}: {chunk}")
            else:
                temp_output.append(f"网页内容: {content}")
        output.append("\n".join(temp_output))

    # 再输出低分结果
    if ignored_results:
        output.append(
            f"执行的搜索查询: {query}\n{len(ignored_results)} 个结果因相关性分数低于阈值 {response.threshold} 而被忽略（可作为补充信息）:"
        )
        for index, result in enumerate(ignored_results, start=1):
            temp_output: list[str] = [f"\n第 {index} 个被忽略的搜索结果的详细信息如下:"]
            temp_output.append(f"标题: {clean_invisible_chars(result.title)}")
            temp_output.append(f"URL: {result.url}")
            if result.score:
                temp_output.append(f"相关性分数: {result.score:.2f}")
            output.append("\n".join(temp_output))

    return "\n".join(output)


def format_multiple_query_search_results(responses: list[TavilySearchResponse]) -> str:
    """
    将多个Tavily Search API 响应格式化为人类可读的文本
    """
    output = []
    for response in responses:
        output.append(format_query_search_results(response))
    return "\n\n----\n\n".join(output)


def format_extract_results(response: TavilyExtractResponse) -> str:
    """
    将 Tavily Extract API 响应格式化为人类可读的文本

    Args:
        response: TavilyExtractResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []
    is_chunked = response.is_chunked

    # Format successful extraction results
    output.append(f"{len(response.results)} 个网页提取结果如下:")
    for index, result in enumerate(response.results, start=1):
        temp_output: list[str] = [f"\n第 {index} 个提取结果的详细信息如下:"]
        temp_output.append(f"标题: {clean_invisible_chars(result.title)}")
        temp_output.append(f"URL: {result.url}")
        raw_content = clean_invisible_chars(result.raw_content)
        if raw_content:
            if is_chunked:
                chunks = raw_content.split("[...]")
                for i, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"相关内容 {i}: {chunk}")
            else:
                temp_output.append(f"提取内容: {raw_content}")
        output.append("\n".join(temp_output))

    if response.failed_results:
        output.append(f"\n{len(response.failed_results)} 个网页提取失败的URL:")
        for index, failed in enumerate(response.failed_results, start=1):
            temp_output: list[str] = [f"\n第 {index} 个提取失败的URL的详细信息如下:"]
            temp_output.append(f"URL: {failed.url}")
            temp_output.append(f"错误: {failed.error}")
            output.append("\n".join(temp_output))

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
    is_chunked = response.is_chunked

    output.append(f"{len(response.results)} 个网页爬取结果如下:")
    output.append(f"爬取的基础URL: {response.base_url}")

    for index, page in enumerate(response.results, start=1):
        temp_output: list[str] = [f"\n第 {index} 个爬取结果的详细信息如下:"]
        temp_output.append(f"爬取的URL: {page.url}")
        raw_content = clean_invisible_chars(page.raw_content)
        if raw_content:
            if is_chunked:
                chunks = raw_content.split("[...]")
                for i, chunk in enumerate(chunks, start=1):
                    temp_output.append(f"相关内容 {i}: {chunk}")
            else:
                temp_output.append(f"爬取内容: {raw_content}")
        output.append("\n".join(temp_output))

    return "\n".join(output)


def filter_search_results_by_score(
    results: list[TavilySearchResultItem],
    threshold: float = 0.5,
) -> tuple[list[TavilySearchResultItem], list[TavilySearchResultItem], float]:
    """
    根据相关性分数过滤搜索结果，优先选择高分结果

    Args:
        results: 搜索结果列表
        threshold: 分数阈值，高于此值的被视为高分结果

    Returns:
        tuple: (过滤后的结果列表, 被忽略的结果列表)
    """

    def _filter_by_threshold(
        items: list[TavilySearchResultItem], thresh: float
    ) -> tuple[list[TavilySearchResultItem], list[TavilySearchResultItem]]:
        """根据阈值过滤结果"""
        high, low = [], []
        for item in items:
            (high if item.score is not None and item.score > thresh else low).append(
                item
            )
        return high, low

    # 初始过滤
    high_score_results, low_score_results = _filter_by_threshold(results, threshold)
    adjusted_threshold = threshold  # 默认使用入参阈值，确保所有分支可返回

    # 如果高分结果数量小于总结果数的一半，动态调整阈值
    if len(high_score_results) < len(results) / 2 and low_score_results:
        first_low_score = low_score_results[0].score
        if first_low_score is not None:
            # 将阈值调整为向下取整到第一位小数（第二位小数置为0）
            # 例如：0.49 -> 0.40, 0.39 -> 0.30
            adjusted_threshold = math.floor(first_low_score * 10) / 10
            high_score_results, low_score_results = _filter_by_threshold(
                results, adjusted_threshold
            )

    # 返回结果：有高分结果则返回高分结果，否则返回第一个低分结果
    if high_score_results:
        return high_score_results, low_score_results, adjusted_threshold
    return (
        low_score_results[:1] if low_score_results else [],
        low_score_results[1:],
        adjusted_threshold,
    )


def format_map_results(response: TavilyMapResponse) -> str:
    """
    将 Tavily Map API 响应格式化为人类可读的文本

    Args:
        response: TavilyMapResponse 对象

    Returns:
        格式化后的字符串
    """
    output = []

    output.append(f"{len(response.results)} 个Site Map Results:")
    output.append(f"Base URL: {response.base_url}")

    output.append(f"\n{len(response.results)} 个Mapped Pages:")
    for index, page in enumerate(response.results, start=1):
        output.append(f"\n第 {index} 个Mapped Page: {page}")

    return "\n".join(output)

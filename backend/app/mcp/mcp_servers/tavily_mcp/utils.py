import math
import re
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment

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


def _xml_text(value: str) -> str:
    """Escape short XML text fields (query / title / url / error)."""
    return xml_escape(value, {"'": "&apos;", '"': "&quot;"})


def _xml_cdata(value: str) -> str:
    """Wrap long body text in CDATA; split any embedded ]]> sequences."""
    safe = value.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _split_snippets(content: str) -> list[str]:
    return [chunk.strip() for chunk in content.split("[...]") if chunk.strip()]


def _prepare_body(
    raw: str, *, is_chunked: bool | None, include_body: bool
) -> dict[str, Any]:
    if not include_body:
        return {"content": None, "snippets": None}
    body = clean_invisible_chars(raw or "")
    if not body:
        return {"content": None, "snippets": None}
    if is_chunked:
        return {"content": None, "snippets": _split_snippets(body)}
    return {"content": body, "snippets": None}


def _prepare_search_result(
    result: TavilySearchResultItem,
    *,
    include_body: bool,
    is_chunked: bool | None,
) -> dict[str, Any]:
    body = _prepare_body(
        result.content or "", include_body=include_body, is_chunked=is_chunked
    )
    return {
        "title": clean_invisible_chars(result.title or ""),
        "url": result.url or "",
        "score": f"{result.score:.2f}" if result.score is not None else None,
        **body,
    }


def _prepare_search_query_context(
    response: TavilySearchResponse, *, include_body: bool
) -> dict[str, Any]:
    is_chunked = response.is_chunked
    high = response.filtered_results or []
    low = response.ignored_results or []
    return {
        "query": response.query,
        "high_results": [
            _prepare_search_result(r, include_body=include_body, is_chunked=is_chunked)
            for r in high
        ],
        "ignored_results": [
            _prepare_search_result(r, include_body=False, is_chunked=is_chunked)
            for r in low
        ],
        "threshold": (
            f"{response.threshold:.2f}" if response.threshold is not None else None
        ),
    }


# ---------------------------------------------------------------------------
# Jinja2 templates (XML for LLM)
# ---------------------------------------------------------------------------

_JINJA_ENV = Environment(autoescape=False)
_JINJA_ENV.filters["xml"] = _xml_text
_JINJA_ENV.filters["cdata"] = _xml_cdata

_BODY_MACRO = """
{%- macro render_body(item) -%}
{%- if item.snippets -%}
{%- for snippet in item.snippets %}
    <snippet index="{{ loop.index }}">{{ snippet|cdata }}</snippet>
{%- endfor -%}
{%- elif item.content %}
    <content>{{ item.content|cdata }}</content>
{%- endif -%}
{%- endmacro -%}
""".strip()

_SEARCH_QUERY_TEMPLATE = _JINJA_ENV.from_string(
    _BODY_MACRO
    + """
{%- macro render_result(item, index) %}
    <result index="{{ index }}">
      <title>{{ item.title|xml }}</title>
      <url>{{ item.url|xml }}</url>
{%- if item.score %}
      <score>{{ item.score }}</score>
{%- endif -%}
{{ render_body(item) }}
    </result>
{%- endmacro -%}

<search_query>
  <query>{{ query|xml }}</query>
{%- if high_results %}
  <high_relevance_results count="{{ high_results|length }}">
{%- for item in high_results -%}
{{ render_result(item, loop.index) }}
{%- endfor %}
  </high_relevance_results>
{%- endif -%}
{%- if ignored_results %}
  <ignored_results count="{{ ignored_results|length }}"{% if threshold %} threshold="{{ threshold }}"{% endif %}>
{%- for item in ignored_results -%}
{{ render_result(item, loop.index) }}
{%- endfor %}
  </ignored_results>
{%- endif %}
</search_query>
""".strip()
)

_WEB_SEARCH_RESULTS_TEMPLATE = _JINJA_ENV.from_string(
    """
<web_search_results>
{%- for q in search_queries %}
{{ q }}
{%- endfor %}
</web_search_results>
""".strip()
)

_EXTRACT_RESULTS_TEMPLATE = _JINJA_ENV.from_string(
    _BODY_MACRO
    + """
<web_extract_results>
{%- if extracts %}
  <extracts count="{{ extracts|length }}">
{%- for item in extracts %}
    <extract index="{{ loop.index }}">
      <title>{{ item.title|xml }}</title>
      <url>{{ item.url|xml }}</url>
{{ render_body(item) }}
    </extract>
{%- endfor %}
  </extracts>
{%- else %}
  <extracts count="0"/>
{%- endif -%}
{%- if failed_extracts %}
  <failed_extracts count="{{ failed_extracts|length }}">
{%- for item in failed_extracts %}
    <failed_extract index="{{ loop.index }}">
      <url>{{ item.url|xml }}</url>
      <error>{{ item.error|xml }}</error>
    </failed_extract>
{%- endfor %}
  </failed_extracts>
{%- endif %}
</web_extract_results>
""".strip()
)

_CRAWL_RESULTS_TEMPLATE = _JINJA_ENV.from_string(
    _BODY_MACRO
    + """
<web_crawl_results>
  <base_url>{{ base_url|xml }}</base_url>
  <pages count="{{ pages|length }}">
{%- for item in pages %}
    <page index="{{ loop.index }}">
      <url>{{ item.url|xml }}</url>
{{ render_body(item) }}
    </page>
{%- endfor %}
  </pages>
</web_crawl_results>
""".strip()
)


def format_query_search_results(response: TavilySearchResponse) -> tuple[str, str]:
    """
    将 Tavily Search API 响应格式化为 XML（供 LLM 消费）。

    Returns:
        (content, summary)：content 含正文；summary 仅含元数据
    """
    content = _SEARCH_QUERY_TEMPLATE.render(
        **_prepare_search_query_context(response, include_body=True)
    ).strip()
    summary = _SEARCH_QUERY_TEMPLATE.render(
        **_prepare_search_query_context(response, include_body=False)
    ).strip()
    return content, summary


def format_multiple_query_search_results(
    responses: list[TavilySearchResponse],
) -> tuple[str, str]:
    """将多个 Tavily Search API 响应格式化为 XML。"""
    content_parts: list[str] = []
    summary_parts: list[str] = []
    for response in responses:
        output_content, summary_content = format_query_search_results(response)
        content_parts.append(output_content)
        summary_parts.append(summary_content)

    content = _WEB_SEARCH_RESULTS_TEMPLATE.render(search_queries=content_parts).strip()
    summary = _WEB_SEARCH_RESULTS_TEMPLATE.render(search_queries=summary_parts).strip()
    return content, summary


def format_extract_results(response: TavilyExtractResponse) -> tuple[str, str]:
    """
    将 Tavily Extract API 响应格式化为 XML。

    Returns:
        (content, summary)：content 含正文；summary 仅含元数据
    """
    is_chunked = response.is_chunked
    extracts_full: list[dict[str, Any]] = []
    extracts_meta: list[dict[str, Any]] = []
    for result in response.results or []:
        base = {
            "title": clean_invisible_chars(result.title or ""),
            "url": result.url or "",
        }
        extracts_full.append(
            {
                **base,
                **_prepare_body(
                    result.raw_content or "",
                    include_body=True,
                    is_chunked=is_chunked,
                ),
            }
        )
        extracts_meta.append({**base, "content": None, "snippets": None})

    failed = [
        {"url": item.url, "error": item.error or ""}
        for item in (response.failed_results or [])
    ]

    content = _EXTRACT_RESULTS_TEMPLATE.render(
        extracts=extracts_full, failed_extracts=failed
    ).strip()
    summary = _EXTRACT_RESULTS_TEMPLATE.render(
        extracts=extracts_meta, failed_extracts=failed
    ).strip()
    return content, summary


def format_crawl_results(response: TavilyCrawlResponse) -> tuple[str, str]:
    """
    将 Tavily Crawl API 响应格式化为 XML。

    Returns:
        (content, summary)：content 含正文；summary 仅含元数据
    """
    is_chunked = response.is_chunked
    pages_full: list[dict[str, Any]] = []
    pages_meta: list[dict[str, Any]] = []
    for page in response.results:
        base = {"url": page.url}
        pages_full.append(
            {
                **base,
                **_prepare_body(
                    page.raw_content or "",
                    include_body=True,
                    is_chunked=is_chunked,
                ),
            }
        )
        pages_meta.append({**base, "content": None, "snippets": None})

    content = _CRAWL_RESULTS_TEMPLATE.render(
        base_url=response.base_url, pages=pages_full
    ).strip()
    summary = _CRAWL_RESULTS_TEMPLATE.render(
        base_url=response.base_url, pages=pages_meta
    ).strip()
    return content, summary


def filter_search_results_by_score(
    results: list[TavilySearchResultItem],
    result_per_query: int,
    threshold: float = 0.1,
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
        high: list[TavilySearchResultItem] = []
        low: list[TavilySearchResultItem] = []
        for item in items:
            (high if item.score is not None and item.score > thresh else low).append(
                item
            )
        return high, low

    # 初始过滤
    high_score_results, low_score_results = _filter_by_threshold(results, threshold)
    adjusted_threshold = threshold  # 默认使用入参阈值，确保所有分支可返回

    # 如果高分结果数量小于总结果数的一半，并且小于每个查询结果数的一半，动态调整阈值
    if (
        len(high_score_results) < len(results) // 2
        and len(high_score_results) < result_per_query // 2
        and low_score_results
    ):
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


def format_map_results(response: TavilyMapResponse) -> tuple[str, str]:
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

    return "\n".join(output), "\n".join(output)

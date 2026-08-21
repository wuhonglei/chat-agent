"""Tavily MCP utils 格式化测试（XML 包裹）。"""

import xml.etree.ElementTree as ET

from app.mcp.mcp_servers.tavily_mcp.models import (
    TavilyCrawlResponse,
    TavilyCrawlResultItem,
    TavilyExtractResponse,
    TavilyExtractResultItem,
    TavilyFailedResultItem,
    TavilySearchResponse,
    TavilySearchResultItem,
)
from app.mcp.mcp_servers.tavily_mcp.utils import (
    _xml_cdata,
    format_crawl_results,
    format_extract_results,
    format_multiple_query_search_results,
    format_query_search_results,
)


def _make_search_response(
    *,
    query: str = "test query",
    high: list[TavilySearchResultItem] | None = None,
    low: list[TavilySearchResultItem] | None = None,
    is_chunked: bool = False,
    threshold: float = 0.10,
) -> TavilySearchResponse:
    return TavilySearchResponse(
        query=query,
        results=(high or []) + (low or []),
        response_time=0.1,
        is_chunked=is_chunked,
        threshold=threshold,
        filtered_results=high or [],
        ignored_results=low or [],
    )


def test_format_query_search_results_xml_structure() -> None:
    high = [
        TavilySearchResultItem(
            title="Result A",
            url="https://example.com/a",
            content="Body A",
            score=0.85,
        ),
        TavilySearchResultItem(
            title="Result B",
            url="https://example.com/b",
            content="Body B",
            score=0.72,
        ),
    ]
    low = [
        TavilySearchResultItem(
            title="Ignored",
            url="https://example.com/low",
            content="should not appear in content body for ignored",
            score=0.05,
        ),
    ]
    response = _make_search_response(high=high, low=low, threshold=0.10)
    content, summary = format_query_search_results(response)

    root = ET.fromstring(content)
    assert root.tag == "search_query"
    assert root.findtext("query") == "test query"

    high_el = root.find("high_relevance_results")
    assert high_el is not None
    assert high_el.get("count") == "2"
    results = high_el.findall("result")
    assert len(results) == 2
    assert results[0].get("index") == "1"
    assert results[0].findtext("title") == "Result A"
    assert results[0].findtext("url") == "https://example.com/a"
    assert results[0].findtext("score") == "0.85"
    assert results[0].findtext("content") == "Body A"

    ignored = root.find("ignored_results")
    assert ignored is not None
    assert ignored.get("count") == "1"
    assert ignored.get("threshold") == "0.10"
    ignored_result = ignored.find("result")
    assert ignored_result is not None
    assert ignored_result.find("content") is None
    assert ignored_result.findtext("title") == "Ignored"

    # summary has same metadata tree but no body
    summary_root = ET.fromstring(summary)
    assert summary_root.find("high_relevance_results/result/content") is None
    assert summary_root.find("high_relevance_results/result/title") is not None
    assert "<content>" not in summary
    assert "<snippet" not in summary


def test_format_query_search_results_chunked_snippets() -> None:
    high = [
        TavilySearchResultItem(
            title="Chunked",
            url="https://example.com/c",
            content="part one[...]part two",
            score=0.9,
        ),
    ]
    response = _make_search_response(high=high, is_chunked=True)
    content, summary = format_query_search_results(response)

    root = ET.fromstring(content)
    snippets = root.findall("high_relevance_results/result/snippet")
    assert len(snippets) == 2
    assert snippets[0].get("index") == "1"
    assert snippets[0].text == "part one"
    assert snippets[1].get("index") == "2"
    assert snippets[1].text == "part two"
    assert root.find("high_relevance_results/result/content") is None
    assert "<snippet" not in summary


def test_format_body_escapes_html_and_cdata_terminator() -> None:
    malicious = "before <script>alert(1)</script> </content> mid ]]> after"
    high = [
        TavilySearchResultItem(
            title='Title with <b>tags</b> & "quotes"',
            url="https://example.com/?a=1&b=2",
            content=malicious,
            score=0.5,
        ),
    ]
    response = _make_search_response(high=high)
    content, _summary = format_query_search_results(response)

    # Must still parse as well-formed XML
    root = ET.fromstring(content)
    title = root.findtext("high_relevance_results/result/title")
    assert title == 'Title with <b>tags</b> & "quotes"'
    url = root.findtext("high_relevance_results/result/url")
    assert url == "https://example.com/?a=1&b=2"
    body = root.findtext("high_relevance_results/result/content")
    assert body is not None
    assert "<script>" in body
    assert "</content>" in body
    assert "]]>" in body

    # CDATA helper splits terminator
    assert "]]]]><![CDATA[>" in _xml_cdata("foo ]]> bar")


def test_format_multiple_query_search_results_wraps_queries() -> None:
    responses = [
        _make_search_response(
            query="q1",
            high=[
                TavilySearchResultItem(
                    title="A", url="https://a.example", content="ca", score=0.8
                )
            ],
        ),
        _make_search_response(
            query="q2",
            high=[
                TavilySearchResultItem(
                    title="B", url="https://b.example", content="cb", score=0.7
                )
            ],
        ),
    ]
    content, summary = format_multiple_query_search_results(responses)

    root = ET.fromstring(content)
    assert root.tag == "web_search_results"
    queries = root.findall("search_query")
    assert len(queries) == 2
    assert queries[0].findtext("query") == "q1"
    assert queries[1].findtext("query") == "q2"
    assert "----" not in content

    summary_root = ET.fromstring(summary)
    assert summary_root.tag == "web_search_results"
    assert (
        summary_root.find("search_query/high_relevance_results/result/content") is None
    )


def test_format_extract_results_xml() -> None:
    response = TavilyExtractResponse(
        results=[
            TavilyExtractResultItem(
                title="Page",
                url="https://example.com/page",
                raw_content="extracted body",
            )
        ],
        failed_results=[
            TavilyFailedResultItem(url="https://bad.example", error="timeout")
        ],
        response_time=0.2,
    )
    content, summary = format_extract_results(response)

    root = ET.fromstring(content)
    assert root.tag == "web_extract_results"
    extracts = root.find("extracts")
    assert extracts is not None
    assert extracts.get("count") == "1"
    extract = extracts.find("extract")
    assert extract is not None
    assert extract.findtext("title") == "Page"
    assert extract.findtext("content") == "extracted body"

    failed = root.find("failed_extracts")
    assert failed is not None
    assert failed.get("count") == "1"
    assert failed.findtext("failed_extract/error") == "timeout"

    summary_root = ET.fromstring(summary)
    assert summary_root.find("extracts/extract/content") is None


def test_format_crawl_results_xml() -> None:
    response = TavilyCrawlResponse(
        base_url="https://example.com",
        results=[
            TavilyCrawlResultItem(
                url="https://example.com/1",
                raw_content="crawl body",
            )
        ],
        response_time=0.3,
    )
    content, summary = format_crawl_results(response)

    root = ET.fromstring(content)
    assert root.tag == "web_crawl_results"
    assert root.findtext("base_url") == "https://example.com"
    pages = root.find("pages")
    assert pages is not None
    assert pages.get("count") == "1"
    page = pages.find("page")
    assert page is not None
    assert page.get("index") == "1"
    assert page.findtext("url") == "https://example.com/1"
    assert page.findtext("content") == "crawl body"

    summary_root = ET.fromstring(summary)
    assert summary_root.find("pages/page/content") is None

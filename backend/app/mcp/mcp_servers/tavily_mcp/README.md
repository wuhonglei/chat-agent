# Tavily Search MCP Server

A Model Context Protocol (MCP) server implementation for the Tavily API, built with FastMCP.

## Tool naming

- MCP 协议层（`list_tools` / 实际 `@mcp.tool(name=...)`）的裸名：`web_search`、`web_pages_extract`、`web_site_crawl`。
- 暴露给 LLM 的名字为 `{server}_{bare}`，即 `tavily_web_search`、`tavily_web_pages_extract`、`tavily_web_site_crawl`（见 `app/mcp/tool_naming.py`）。

## Features

This MCP server provides 3 tools for web search, content extraction and crawling:

### 1. web_search (LLM: `tavily_web_search`)

基于 Tavily AI 搜索引擎的网页搜索，返回实时、相关的网页内容。

主要参数：

- `queries: list[str]` — 搜索查询列表（简单问题 1 个，复杂问题 2-3 个）
- `topic: "general" | "news" | "finance"` — 搜索类别（默认 `general`）
- `search_depth: "advanced" | "basic" | "fast" | "ultra-fast"` — 搜索深度（默认 `advanced`）
- `chunks_per_source: int` — 每个来源的相关片段上限（1-5，默认 3；仅 `advanced`/`fast` 可用）
- `result_per_query: int` — 每个查询返回结果数（1-20，默认 5）
- `time_range`、`start_date`、`end_date` — 时间过滤（日期格式 `YYYY-MM-DD`）
- `include_domains`、`exclude_domains` — 域名包含/排除
- `country` — 提升特定国家结果（仅 `topic="general"` 可用）

### 2. web_pages_extract (LLM: `tavily_web_pages_extract`)

从指定 URL 提取并处理原始内容。

主要参数：

- `urls: list[str]` — 要提取内容的 URL 列表（最多 100 个）
- `query: str | None` — 用于对提取片段重排的用户意图
- `extract_depth: "advanced" | "basic"` — 提取深度（默认 `advanced`）

### 3. web_site_crawl (LLM: `tavily_web_site_crawl`)

从基础 URL 开始进行结构化网页爬取，沿内部链接跨页扩展。

主要参数：

- `url: str` — 开始爬取的根 URL
- `instructions: str | None` — 自然语言爬取指令
- `max_depth: int` — 最大爬取深度（1-3，默认 1）
- `max_breadth: int` — 每层最多跟随的链接数（1-50，默认 20）
- `limit: int` — 处理链接总数上限（1-200，默认 50）
- `select_paths`、`select_domains`、`exclude_paths`、`exclude_domains` — 正则过滤
- `allow_external: bool` — 是否包含外部链接（默认 `True`）
- `extract_depth: "basic" | "advanced"` — 提取深度（默认 `basic`）

## Installation

### Prerequisites

- Python 3.10+
- Tavily API Key（从 [Tavily](https://app.tavily.com/) 获取）

### Setup

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 编辑 `.env` 并填入 API key：

```
TAVILY_API_KEY=your_actual_api_key_here
```

## Usage

### Running as HTTP Server (Default)

```bash
python server.py
```

默认监听 8002 端口。使用其他端口：

```bash
python server.py --port 8003
```

### Running as Stdio Server

```bash
python server.py --transport stdio
```

## Tool Examples

> 以下示例以裸名调用，便于说明参数；在 Agent / LLM 侧实际工具名为 `tavily_` 前缀版本。

### web_search

```python
result = web_search(
    queries=["latest AI developments"],
    result_per_query=5,
)

result = web_search(
    queries=["technology news"],
    topic="news",
    time_range="week",
    result_per_query=10,
)
```

### web_pages_extract

```python
result = web_pages_extract(
    urls=["https://example.com/article"],
    extract_depth="basic",
)
```

### web_site_crawl

```python
result = web_site_crawl(
    url="https://docs.example.com",
    instructions="Only crawl documentation pages",
    max_depth=3,
    select_paths=["/docs/.*"],
)
```

## Response Format

工具内部仍用 Pydantic 模型校验 Tavily API（`models.py` 的 `TavilySearchResponse` / `TavilyExtractResponse` / `TavilyCrawlResponse`）。**返回给 LLM 的 `content` / `summary` 已格式化为 XML**（`utils.py` 的 `format_*_results`），不再把 JSON 原文直接塞进 tool_result。

| 工具 | 根节点 | content | summary |
|------|--------|---------|---------|
| `web_search` | `<web_search_results>` 包一层或多层 `<search_query>` | 含正文：`is_chunked` 时用 `<snippet>`，否则 `<content>` CDATA | 同结构，不含 body |
| `web_pages_extract` | `<web_extract_results>` | `<extracts>` + 可选 `<failed_extracts>` | 仅 title/url/error |
| `web_site_crawl` | `<web_crawl_results>` | `<base_url>` + `<pages>` | 仅 url，无正文 |

搜索结果按阈值拆成 `<high_relevance_results>` 与 `<ignored_results>`；ignored 条目 **不带正文**（只留 title/url/score）。短字段走 XML escape，长正文走 CDATA（内嵌 `]]>` 会拆段）。出错时仍抛原始异常。

示例（单 query search 的 content）：

```xml
<search_query>
  <query>latest AI developments</query>
  <high_relevance_results count="1">
    <result index="1">
      <title>Example</title>
      <url>https://example.com</url>
      <score>0.85</score>
      <content><![CDATA[Body text]]></content>
    </result>
  </high_relevance_results>
</search_query>
```

多 query 时再用 `<web_search_results>` 包裹各 `<search_query>`。`chunks_per_source` 生效（`is_chunked=true`）时，正文拆成多个 `<snippet index="N">`，而不是单一 `<content>`。

## API Documentation

- [Tavily Documentation](https://docs.tavily.com/)
- [Tavily API Reference](https://docs.tavily.com/api-reference)

## License

This MCP server is built for the chat-agent project.

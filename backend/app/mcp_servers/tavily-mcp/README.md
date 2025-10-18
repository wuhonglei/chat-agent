# Tavily Search MCP Server

A Model Context Protocol (MCP) server implementation for Tavily Search API, built with FastMCP.

## Features

This MCP server provides 4 powerful tools for web search and content extraction:

### 1. tavily_search
A comprehensive web search tool powered by Tavily's AI search engine.

**Key Features:**
- Real-time web search with basic/advanced depth options
- Topic filtering (general/news)
- Time-based filtering (days, time_range, date ranges)
- Domain inclusion/exclusion
- Country-specific search boosting
- Image results with descriptions
- Raw HTML content extraction

### 2. tavily_extract
Extract and process raw content from specified URLs.

**Key Features:**
- Basic and advanced extraction modes
- Support for multiple URLs
- Image extraction
- Markdown or text output format
- LinkedIn-optimized extraction (use advanced mode)

### 3. tavily_crawl
Structured web crawling starting from a base URL.

**Key Features:**
- Configurable depth and breadth limits
- Natural language instructions for crawler
- Regex-based path and domain filtering
- Internal and external link handling
- Advanced content extraction with tables and embedded content

### 4. tavily_map
Create structured site maps and discover website architecture.

**Key Features:**
- Website structure analysis
- Navigation path discovery
- Configurable exploration limits
- Domain and path filtering
- Content organization insights

## Installation

### Prerequisites

- Python 3.10+
- Tavily API Key (get it from [Tavily](https://app.tavily.com/))

### Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and add your Tavily API key:
```
TAVILY_API_KEY=your_actual_api_key_here
```

3. Install dependencies (if not already installed):
```bash
pip install fastmcp httpx pydantic
```

## Usage

### Running as HTTP Server (Default)

```bash
python server.py
```

The server will start on port 8002 by default.

To use a different port:
```bash
python server.py --port 8003
```

### Running as Stdio Server

```bash
python server.py --transport stdio
```

## Tool Examples

### Search Example

```python
# Basic search
result = tavily_search(
    query="latest AI developments",
    max_results=5
)

# News search with time filter
result = tavily_search(
    query="technology news",
    topic="news",
    days=7,
    max_results=10
)

# Country-specific search
result = tavily_search(
    query="startup news",
    country="united states",
    max_results=5
)
```

### Extract Example

```python
# Extract content from URLs
result = tavily_extract(
    urls=["https://example.com/article"],
    extract_depth="basic",
    format="markdown"
)

# Advanced extraction for LinkedIn
result = tavily_extract(
    urls=["https://linkedin.com/in/someone"],
    extract_depth="advanced",
    format="markdown",
    include_images=True
)
```

### Crawl Example

```python
# Basic crawl
result = tavily_crawl(
    url="https://example.com",
    max_depth=2,
    max_breadth=10
)

# Crawl with instructions and filters
result = tavily_crawl(
    url="https://docs.example.com",
    max_depth=3,
    instructions="Only crawl documentation pages",
    select_paths=["/docs/.*"],
    format="markdown"
)
```

### Map Example

```python
# Create site map
result = tavily_map(
    url="https://example.com",
    max_depth=2,
    limit=100
)

# Map with domain filtering
result = tavily_map(
    url="https://docs.example.com",
    select_domains=["^docs\\.example\\.com$"],
    allow_external=False
)
```

## Response Format

All tools return a dictionary with the following structure:

```python
{
    "formatted": "Human-readable formatted results",
    "raw": {
        # Original API response data
    }
}
```

In case of errors:
```python
{
    "error": "Error message"
}
```

## API Documentation

For detailed API documentation, visit:
- [Tavily Documentation](https://docs.tavily.com/)
- [Tavily API Reference](https://docs.tavily.com/api-reference)

## License

This MCP server is built for the AI-Doc project.

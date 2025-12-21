"""Tavily Search API models"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class TavilySearchResultItem(BaseModel):
    """Individual search result from Tavily API"""

    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    content: str = Field(..., description="Short description/snippet of the result")
    score: float = Field(..., description="Relevance score of the result")
    raw_content: Optional[str] = Field(None, description="Cleaned HTML content of the page")
    favicon: Optional[str] = Field(None, description="Favicon URL for the result")


class TavilyAutoParameters(BaseModel):
    """Auto-selected search parameters by Tavily"""

    search_depth: Optional[str] = Field(None, description="Auto-selected search depth")
    include_domains: Optional[list[str]] = Field(None, description="Auto-selected domains to include")
    exclude_domains: Optional[list[str]] = Field(None, description="Auto-selected domains to exclude")


class TavilySearchResponse(BaseModel):
    """Complete response from Tavily Search API"""

    query: str = Field(..., description="The original search query executed")
    answer: Optional[str] = Field(None, description="LLM-generated short answer to the query")
    images: list[str] = Field(default_factory=list, description="List of query-related image URLs")
    results: list[TavilySearchResultItem] = Field(default_factory=list, description="Ranked search results")
    auto_parameters: Optional[TavilyAutoParameters] = Field(None, description="Auto-selected search parameters")
    response_time: Optional[float] = Field(None, description="Request processing time in seconds")
    request_id: Optional[str] = Field(None, description="Unique identifier for the request")


class TavilySearchRequest(BaseModel):
    """Request parameters for Tavily Search API"""

    query: str = Field(..., description="Search query")
    search_depth: str = Field("basic", description="Search depth: 'basic' or 'advanced'")
    include_answer: bool = Field(False, description="Include AI-generated answer")
    include_raw_content: bool = Field(False, description="Include raw HTML content")
    max_results: int = Field(10, description="Maximum number of results (1-20)")
    include_images: bool = Field(False, description="Include image results")
    include_domains: Optional[list[str]] = Field(None, description="Domains to include")
    exclude_domains: Optional[list[str]] = Field(None, description="Domains to exclude")
    days: Optional[int] = Field(None, description="Filter results from the last N days")
    auto_parameters: bool = Field(True, description="Enable automatic parameter selection")
    include_favicon: bool = Field(True, description="Include favicon URLs")
    chunks_per_source: Optional[int] = Field(None, description="Number of content chunks per source")
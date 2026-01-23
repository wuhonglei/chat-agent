from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.tavily_mcp import utils as tavily_utils
from app.mcp.mcp_servers.tavily_mcp.models import (
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilySearchResponse,
)
from app.utils.context_compactor import CompactionResult, ContextCompactor


class TavilyResultProcessor:
    WEB_SEARCH = "web_search"
    WEB_PAGES_EXTRACT = "web_pages_extract"
    WEB_SITE_CRAWL = "web_site_crawl"

    def __init__(
        self, compactor: ContextCompactor, query: str, threshold_tokens_count: int
    ) -> None:
        self.compactor = compactor
        self.query = query
        self.threshold_tokens_count = threshold_tokens_count

    async def format_result(
        self, tool_name: str, structured_content: dict[str, Any]
    ) -> CompactionResult:
        if tool_name == self.WEB_SEARCH:
            payload = TavilySearchResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_search_response(
                payload, self.threshold_tokens_count
            )
            formatted = tavily_utils.format_search_results(payload)
            compaction_result.content = formatted
            return compaction_result

        if tool_name == self.WEB_PAGES_EXTRACT:
            payload = TavilyExtractResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_extract_response(
                payload, self.threshold_tokens_count
            )
            formatted = tavily_utils.format_extract_results(payload)
            compaction_result.content = formatted
            return compaction_result

        if tool_name == self.WEB_SITE_CRAWL:
            payload = TavilyCrawlResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_crawl_response(
                payload, self.threshold_tokens_count
            )
            formatted = tavily_utils.format_crawl_results(payload)
            compaction_result.content = formatted
            return compaction_result

        # Fallback for unknown tools - try to get content from structured_content
        content = structured_content.get("content")
        if content:
            return await self._compact_content(content, self.threshold_tokens_count)
        else:
            # If no content key, return empty compaction result
            return CompactionResult(
                content=str(structured_content),
                relevance_applied=False,
                content_token_count=0,
                original_token_count=0,
                relevant_token_count=0,
                threshold_token_count=0,
            )

    async def _compact_search_response(
        self,
        data: TavilySearchResponse,
        threshold_tokens_count: int,
    ) -> tuple[TavilySearchResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.filtered_results or [],
            "content",
            threshold_tokens_count,
        )
        return data, compaction_result

    async def _compact_extract_response(
        self,
        data: TavilyExtractResponse,
        threshold_tokens_count: int,
    ) -> tuple[TavilyExtractResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.results or [],
            "raw_content",
            threshold_tokens_count,
        )
        return data, compaction_result

    async def _compact_crawl_response(
        self,
        data: TavilyCrawlResponse,
        threshold_tokens_count: int,
    ) -> tuple[TavilyCrawlResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.results or [],
            "raw_content",
            threshold_tokens_count,
        )
        return data, compaction_result

    async def _compact_items(
        self, items: list[Any], content_attr: str, threshold_tokens_count: int
    ) -> CompactionResult:
        compaction_result = CompactionResult(
            content="",
            relevance_applied=False,
            content_token_count=0,
            original_token_count=0,
            relevant_token_count=0,
            threshold_token_count=0,
        )
        for item in items:
            if not item:
                continue
            content = getattr(item, content_attr, None)
            if not content:
                continue
            compaction = await self.compactor.compact_markdown_tool_result(
                query=self.query,
                content=content,
                threshold_tokens_count=threshold_tokens_count,
            )
            if compaction.relevance_applied:
                compaction_result.relevance_applied = True
            compaction_result.content_token_count += compaction.content_token_count
            compaction_result.original_token_count += compaction.original_token_count
            compaction_result.relevant_token_count += compaction.relevant_token_count
            compaction_result.threshold_token_count += compaction.threshold_token_count
            setattr(item, content_attr, compaction.content)
        return compaction_result

    async def _compact_content(
        self, content: str, threshold_tokens_count: int
    ) -> CompactionResult:
        return await self.compactor.compact_markdown_tool_result(
            query=self.query,
            content=content,
            threshold_tokens_count=threshold_tokens_count,
        )

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.tavily_mcp import utils as tavily_utils
from app.mcp.mcp_servers.tavily_mcp.models import (
    MultipleTavilySearchResponse,
    TavilyCrawlResponse,
    TavilyExtractResponse,
    TavilySearchResponse,
    TavilySearchResultItem,
)
from app.utils.context_compactor import CompactionResult, ContextCompactor


class TavilyResultProcessor:
    WEB_SEARCH = "web_search"
    WEB_PAGES_EXTRACT = "web_pages_extract"
    WEB_SITE_CRAWL = "web_site_crawl"

    def __init__(
        self,
        compactor: ContextCompactor,
        user_query: str,
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
    ) -> None:
        self.compactor = compactor
        self.user_query = user_query
        self.tolerance_tokens_count = tolerance_tokens_count
        self.threshold_tokens_count = threshold_tokens_count

    async def format_result(
        self, tool_name: str, structured_content: dict[str, Any]
    ) -> CompactionResult:
        if tool_name == self.WEB_SEARCH:
            search_payload = MultipleTavilySearchResponse.model_validate(
                structured_content
            )
            data, compaction_result = await self._compact_search_response(
                search_payload.results,
                self.tolerance_tokens_count,
                self.threshold_tokens_count,
            )
            content, summary = tavily_utils.format_multiple_query_search_results(data)
            compaction_result.content = content
            compaction_result.summary = summary
            compaction_result.structured_content_for_display = (
                self._build_search_display_items(data)
            )
            return compaction_result

        if tool_name == self.WEB_PAGES_EXTRACT:
            extract_payload = TavilyExtractResponse.model_validate(structured_content)
            extract_payload, compaction_result = await self._compact_extract_response(
                extract_payload,
                self.tolerance_tokens_count,
                self.threshold_tokens_count,
            )
            content, summary = tavily_utils.format_extract_results(extract_payload)
            compaction_result.content = content
            compaction_result.summary = summary
            return compaction_result

        if tool_name == self.WEB_SITE_CRAWL:
            crawl_payload = TavilyCrawlResponse.model_validate(structured_content)
            crawl_payload, compaction_result = await self._compact_crawl_response(
                crawl_payload,
                self.tolerance_tokens_count,
                self.threshold_tokens_count,
            )
            content, summary = tavily_utils.format_crawl_results(crawl_payload)
            compaction_result.content = content
            compaction_result.summary = summary
            return compaction_result

        # Fallback for unknown tools - try to get content from structured_content
        raw_content = structured_content.get("content")
        if isinstance(raw_content, str):
            return await self._compact_content(
                raw_content, self.tolerance_tokens_count, self.threshold_tokens_count
            )
        else:
            # If no content key, return empty compaction result
            return CompactionResult(
                content=str(structured_content),
                summary=str(structured_content),
                relevance_applied=False,
                content_token_count=0,
                original_token_count=0,
                relevant_token_count=0,
                threshold_token_count=0,
            )

    async def _compact_search_response(
        self,
        data: list[TavilySearchResponse],
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
    ) -> tuple[list[TavilySearchResponse], CompactionResult]:
        compaction_result = CompactionResult(
            content="",
            summary=None,
            relevance_applied=False,
            content_token_count=0,
            original_token_count=0,
            relevant_token_count=0,
            threshold_token_count=0,
        )
        for item in data:
            compaction = await self._compact_items(
                item.query or self.user_query,
                item.filtered_results or [],
                "content",
                tolerance_tokens_count,
                threshold_tokens_count,
            )
            if compaction.relevance_applied:
                compaction_result.relevance_applied = True
            compaction_result.content_token_count += compaction.content_token_count
            compaction_result.original_token_count += compaction.original_token_count
            compaction_result.relevant_token_count += compaction.relevant_token_count
            compaction_result.threshold_token_count += compaction.threshold_token_count
        return data, compaction_result

    async def _compact_extract_response(
        self,
        data: TavilyExtractResponse,
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
    ) -> tuple[TavilyExtractResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.query or self.user_query,
            data.results or [],
            "raw_content",
            tolerance_tokens_count,
            threshold_tokens_count,
        )
        return data, compaction_result

    async def _compact_crawl_response(
        self,
        data: TavilyCrawlResponse,
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
    ) -> tuple[TavilyCrawlResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            self.user_query,
            data.results or [],
            "raw_content",
            tolerance_tokens_count,
            threshold_tokens_count,
        )
        return data, compaction_result

    async def _compact_items(
        self,
        query: str,
        items: list[Any],
        content_attr: str,
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
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
                query=query,
                content=content,
                tolerance_tokens_count=tolerance_tokens_count,
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
        self, content: str, tolerance_tokens_count: int, threshold_tokens_count: int
    ) -> CompactionResult:
        return await self.compactor.compact_markdown_tool_result(
            query=self.user_query,
            content=content,
            tolerance_tokens_count=tolerance_tokens_count,
            threshold_tokens_count=threshold_tokens_count,
        )

    def _build_search_display_items(
        self, responses: list[TavilySearchResponse]
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for response in responses:
            items.append(
                {
                    "query": response.query,
                    "results": self._build_search_result_items(
                        response.filtered_results or [],
                    ),
                }
            )
        return items

    def _build_search_result_items(
        self,
        results: list[TavilySearchResultItem],
    ) -> list[dict[str, Any]]:
        return [
            {
                "title": result.title,
                "url": result.url,
                "score": result.score,
                "favicon": result.favicon,
            }
            for result in results
        ]

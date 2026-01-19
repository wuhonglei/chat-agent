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
    def __init__(self, compactor: ContextCompactor, query: str) -> None:
        self.compactor = compactor
        self.query = query

    async def format_result(
        self, tool_name: str, structured_content: dict[str, Any]
    ) -> CompactionResult:
        if tool_name == "web_search":
            payload = TavilySearchResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_search_response(payload)
            formatted = tavily_utils.format_search_results(payload)
            compaction_result.content = formatted
            return compaction_result

        if tool_name == "url_content_extract":
            payload = TavilyExtractResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_extract_response(payload)
            formatted = tavily_utils.format_extract_results(payload)
            compaction_result.content = formatted
            return compaction_result

        if tool_name == "site_crawl_extract":
            payload = TavilyCrawlResponse.model_validate(structured_content)
            payload, compaction_result = await self._compact_crawl_response(payload)
            formatted = tavily_utils.format_crawl_results(payload)
            compaction_result.content = formatted
            return compaction_result

        return await self._compact_content(structured_content["content"])

    async def _compact_search_response(
        self, data: TavilySearchResponse
    ) -> tuple[TavilySearchResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.filtered_results or [],
            "content",
        )
        return data, compaction_result

    async def _compact_extract_response(
        self, data: TavilyExtractResponse
    ) -> tuple[TavilyExtractResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.results or [],
            "raw_content",
        )
        return data, compaction_result

    async def _compact_crawl_response(
        self, data: TavilyCrawlResponse
    ) -> tuple[TavilyCrawlResponse, CompactionResult]:
        compaction_result = await self._compact_items(
            data.results or [],
            "raw_content",
        )
        return data, compaction_result

    async def _compact_items(
        self, items: list[Any], content_attr: str
    ) -> CompactionResult:
        compaction_result = CompactionResult(
            content="",
            relevance_applied=False,
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
            )
            if compaction.relevance_applied:
                compaction_result.relevance_applied = True
            compaction_result.original_token_count += compaction.original_token_count
            compaction_result.relevant_token_count += compaction.relevant_token_count
            compaction_result.threshold_token_count += compaction.threshold_token_count
            setattr(item, content_attr, compaction.content)
        return compaction_result

    async def _compact_content(self, content: str) -> CompactionResult:
        return await self.compactor.compact_markdown_tool_result(
            query=self.query,
            content=content,
        )

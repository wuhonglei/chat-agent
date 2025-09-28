"""Retrieval manager for coordinating multiple retrieval sources"""

import asyncio
import time
from http import HTTPStatus

from loguru import logger
from rank_bm25 import BM25Okapi
import dashscope

from app.core.config import settings
from app.core.vector_store import VectorManager
from app.models.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    RetrievalSource,
)
from app.services.retrievers.factory import RetrieverFactory


class RetrievalManager:
    """Manager for coordinating retrieval from multiple sources"""

    def __init__(self, vector_manager: VectorManager):
        self.factory = RetrieverFactory(vector_manager)
        self.config = settings

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """
        Retrieve from multiple sources and combine results

        Args:
            request: Retrieval request

        Returns:
            Combined retrieval response
        """
        start_time = time.time()
        all_results = []
        sources_used = []

        # Create tasks for parallel retrieval
        tasks = []
        for source in request.sources:
            retriever = self.factory.get_retriever(source)
            if retriever:
                task = asyncio.create_task(
                    self._retrieve_from_source(retriever, request, source))
                tasks.append(task)
                sources_used.append(source)
            else:
                logger.warning(f"Retriever not available for source: {source}")

        # Wait for all retrievals to complete
        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results from all sources
            for results in results_list:
                if isinstance(results, list):
                    all_results.extend(results)
                elif isinstance(results, Exception):
                    logger.error(f"Retrieval task failed: {results}")

        # Sort by score (descending)
        all_results.sort(key=lambda x: x.score, reverse=True)

        # Apply reranking if enabled
        if self.config.USE_RERANK and len(all_results) > 1 and request.sources != [RetrievalSource.WEB_SEARCH]:
            all_results = await self._rerank_results(request.query, all_results)

        # Limit results
        final_results = all_results[: request.max_results]

        processing_time = (time.time() - start_time) * \
            1000  # Convert to milliseconds

        response = RetrievalResponse(
            results=final_results,
            query=request.query,
            total_results=len(final_results),
            sources_used=sources_used,
            processing_time_ms=processing_time,
        )

        logger.info(
            f"Retrieved {len(final_results)} results from {len(sources_used)} sources "
            f"for query '{request.query}' in {processing_time:.2f}ms"
        )

        return response

    async def _retrieve_from_source(
        self, retriever, request: RetrievalRequest, source: RetrievalSource
    ) -> list[RetrievalResult]:
        """Retrieve from a single source with error handling"""
        try:
            return await retriever.retrieve(request)
        except Exception as e:
            logger.error(f"Failed to retrieve from {source}: {e}")
            return []

    async def health_check(self) -> dict:
        """Check health of all retrieval sources"""
        return await self.factory.health_check()

    def get_available_sources(self) -> list[RetrievalSource]:
        """Get list of available retrieval sources"""
        return self.factory.get_available_retrievers()

    def reload_retrievers(self):
        """Reload all retrievers"""
        self.factory.reload_retrievers()

    async def _rerank_results(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int = None,
    ) -> list[RetrievalResult]:
        """Rerank search results based on query"""
        if not self.config.USE_RERANK or len(results) <= 1:
            return results

        top_k = top_k or self.config.RERANK_TOP_K

        # If cross-encoder is available, use it
        if self.config.RE_RANK_MODEL:
            return await self._rerank_with_dashscope(query, results, top_k)
        else:
            # Fallback to BM25 reranking
            return await self._rerank_with_bm25(query, results, top_k)

    async def _rerank_with_dashscope(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Rerank using cross-encoder model"""
        # Prepare pairs for cross-encoder
        documents = [result.content for result in results]

        # Get scores from cross-encoder asynchronously
        def _call_dashscope():
            return dashscope.TextReRank.call(
                model=self.config.RE_RANK_MODEL,
                api_key=self.config.RE_RANK_API_KEY,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=False
            )

        # Run the synchronous call in a thread pool
        resp = await asyncio.to_thread(_call_dashscope)

        if resp.status_code != HTTPStatus.OK:
            logger.error(
                f"Failed to rerank with dashscope: {resp.status_code}")
            return results[:top_k]

        new_results = []
        for result in resp.output.results:
            if result.relevance_score >= self.config.MIN_RELEVANCE_SCORE:
                results[result.index].score = result.relevance_score
                new_results.append(results[result.index])

        return new_results[:top_k]

    async def _rerank_with_bm25(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Rerank using BM25 algorithm"""
        # Tokenize documents
        tokenized_docs = [result.content.split() for result in results]

        # Initialize BM25
        bm25 = BM25Okapi(tokenized_docs)

        # Get BM25 scores
        tokenized_query = query.split()
        bm25_scores = bm25.get_scores(tokenized_query)

        # Normalize BM25 scores
        max_score = max(bm25_scores) if max(bm25_scores) > 0 else 1
        normalized_scores = [score / max_score for score in bm25_scores]

        # Update scores and sort
        for i, result in enumerate(results):
            # Combine original score with BM25 score
            result.score = 0.5 * result.score + 0.5 * normalized_scores[i]

        # Sort by new scores
        results.sort(key=lambda x: x.score, reverse=True)

        # Filter by minimum relevance score
        filtered_results = [r for r in results if r.score >=
                            self.config.MIN_RELEVANCE_SCORE]

        return filtered_results[:top_k] if filtered_results else results[:top_k]

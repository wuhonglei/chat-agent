"""Retrieval manager for coordinating multiple retrieval sources"""

import asyncio
import time

from loguru import logger

from app.core.vector_store import VectorStore
from app.models.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    RetrievalSource,
)
from app.services.retrievers.factory import RetrieverFactory


class RetrievalManager:
    """Manager for coordinating retrieval from multiple sources"""

    def __init__(self, vector_store: VectorStore):
        self.factory = RetrieverFactory(vector_store)

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
                task = asyncio.create_task(self._retrieve_from_source(retriever, request, source))
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

        # Limit results
        final_results = all_results[: request.max_results]

        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds

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

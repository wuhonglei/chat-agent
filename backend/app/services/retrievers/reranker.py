"""Document reranking module for improving retrieval results"""

import asyncio
from http import HTTPStatus
from typing import List, Optional

import dashscope
from loguru import logger
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.models.retrieval import RetrievalResult


class Reranker:
    """Reranker for improving retrieval results"""

    def __init__(self):
        self.config = settings

    async def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """
        Rerank search results based on query

        Args:
            query: Search query
            results: List of retrieval results to rerank
            top_k: Number of top results to return

        Returns:
            Reranked list of retrieval results
        """
        # If cross-encoder is available, use it
        if self.config.RE_RANK_MODEL:
            logger.info(
                f"Reranking with DashScope model: {self.config.RE_RANK_MODEL}")
            return await self._rerank_with_dashscope(query, results, top_k)
        else:
            # Fallback to BM25 reranking
            logger.info(
                f"Reranking with BM25")
            return await self._rerank_with_bm25(query, results, top_k)

    async def _rerank_with_dashscope(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """
        Rerank using DashScope cross-encoder model

        Args:
            query: Search query
            results: List of retrieval results
            top_k: Number of top results to return

        Returns:
            Reranked results using cross-encoder
        """
        try:
            # Prepare documents for cross-encoder
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
                return results if top_k is None else results[:top_k]

            # Build reranked results
            new_results = []
            for result in resp.output.results:
                if result.relevance_score >= self.config.MIN_RELEVANCE_SCORE:
                    results[result.index].score = result.relevance_score
                    new_results.append(results[result.index])

            return new_results

        except Exception as e:
            logger.error(f"Error in DashScope reranking: {e}")
            # Fallback to original results
            return results[:top_k]

    async def _rerank_with_bm25(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        Rerank using BM25 algorithm

        Args:
            query: Search query
            results: List of retrieval results
            top_k: Number of top results to return

        Returns:
            Reranked results using BM25
        """
        try:
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
            filtered_results = [
                r for r in results
                if r.score >= self.config.MIN_RELEVANCE_SCORE
            ]

            return filtered_results[:top_k] if filtered_results else results[:top_k]

        except Exception as e:
            logger.error(f"Error in BM25 reranking: {e}")
            # Fallback to original results
            return results[:top_k]


class CrossEncoderReranker(Reranker):
    """Cross-encoder based reranker using DashScope"""

    def __init__(self, model: str = None, api_key: str = None):
        super().__init__()
        self.model = model or self.config.RE_RANK_MODEL
        self.api_key = api_key or self.config.RE_RANK_API_KEY

    async def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Rerank using cross-encoder model only"""
        if not self.model:
            logger.warning(
                "No cross-encoder model configured, returning original results")
            return results

        top_k = top_k or self.config.RERANK_TOP_K
        return await self._rerank_with_dashscope(query, results, top_k)


class BM25Reranker(Reranker):
    """BM25 algorithm based reranker"""

    async def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Rerank using BM25 algorithm only"""
        top_k = top_k or self.config.RERANK_TOP_K
        return await self._rerank_with_bm25(query, results, top_k)

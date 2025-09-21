"""Reranker service for improving search results"""

from rank_bm25 import BM25Okapi
import dashscope
from loguru import logger
from http import HTTPStatus

from app.core.config import settings
from app.models.retrieval import RetrievalResult


class Reranker:
    """Rerank search results for better relevance"""

    def __init__(self, config=None):
        # 使用依赖注入模式，允许传入配置或使用默认配置
        self.config = config or settings
        # Initialize cross-encoder for reranking
        # Using a lightweight model for MVP
        pass

    async def rerank(
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
            return self._rerank_with_dashscope(query, results, top_k)
        else:
            # Fallback to BM25 reranking
            return self._rerank_with_bm25(query, results, top_k)

    def _rerank_with_dashscope(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Rerank using cross-encoder model"""
        # Prepare pairs for cross-encoder
        documents = [result.content for result in results]

        # Get scores from cross-encoder
        resp = dashscope.TextReRank.call(
            model=self.config.RE_RANK_MODEL,
            api_key=self.config.RE_RANK_API_KEY,
            query=query,
            documents=documents,
            top_n=top_k,
            return_documents=False
        )

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

    def _rerank_with_bm25(
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

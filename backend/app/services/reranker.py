"""Reranker service for improving search results"""

from typing import List

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.models.document import SearchResult


class Reranker:
    """Rerank search results for better relevance"""

    def __init__(self):
        # Initialize cross-encoder for reranking
        # Using a lightweight model for MVP
        self.cross_encoder = None
        try:
            self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except:
            # Fallback to BM25 if cross-encoder fails to load
            pass

    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = None,
    ) -> List[SearchResult]:
        """Rerank search results based on query"""
        if not results:
            return results

        top_k = top_k or settings.RERANK_TOP_K

        # If cross-encoder is available, use it
        if self.cross_encoder:
            return self._rerank_with_cross_encoder(query, results, top_k)
        else:
            # Fallback to BM25 reranking
            return self._rerank_with_bm25(query, results, top_k)

    def _rerank_with_cross_encoder(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """Rerank using cross-encoder model"""
        # Prepare pairs for cross-encoder
        pairs = [[query, result.content] for result in results]

        # Get scores from cross-encoder
        scores = self.cross_encoder.predict(pairs)

        # Update scores and sort
        for i, result in enumerate(results):
            # Combine original score with reranking score
            result.score = 0.3 * result.score + 0.7 * float(scores[i])

        # Sort by new scores
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def _rerank_with_bm25(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
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
        filtered_results = [r for r in results if r.score >= settings.MIN_RELEVANCE_SCORE]

        return filtered_results[:top_k] if filtered_results else results[:top_k]

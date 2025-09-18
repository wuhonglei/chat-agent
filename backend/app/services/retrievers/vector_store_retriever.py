"""Vector store retriever implementation"""

from loguru import logger

from app.core.vector_store import VectorStore
from app.models.retrieval import RetrievalRequest, RetrievalResult, RetrievalSource
from app.services.retrievers.base import BaseRetriever


class VectorStoreRetriever(BaseRetriever):
    """Retriever for vector store (knowledge base)"""

    def __init__(self, vector_store: VectorStore):
        super().__init__("VectorStore")
        self.vector_store = vector_store

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Retrieve from vector store"""
        try:
            # Search vector store
            search_results = await self.vector_store.search(
                request.query, top_k=request.max_results
            )

            # Convert to retrieval results
            results = []
            for result in search_results:
                if result.score >= request.min_score:
                    retrieval_result = RetrievalResult(
                        content=result.content,
                        title=result.metadata.get("document_name"),
                        source=RetrievalSource.KNOWLEDGE_BASE,
                        score=result.score,
                        metadata={
                            "document_id": result.metadata.get("document_id"),
                            "document_name": result.metadata.get("document_name"),
                            "chunk_id": result.metadata.get("chunk_id"),
                            **result.metadata,
                        },
                    )
                    results.append(retrieval_result)

            logger.info(f"Vector store retrieved {len(results)} results for query: {request.query}")
            return results

        except Exception as e:
            logger.error(f"Vector store retrieval failed: {e}")
            return []

    async def health_check(self) -> bool:
        """Check vector store health"""
        try:
            # Try a simple search to verify connection
            await self.vector_store.search("test", top_k=1)
            return True
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False

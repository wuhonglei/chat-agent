"""Vector store retriever implementation"""

from loguru import logger

from app.core.vector_store import VectorManager, VectorStoreType
from app.models.retrieval import RetrievalRequest, RetrievalResult, RetrievalSource
from app.services.retrievers.base import BaseRetriever


class VectorStoreRetriever(BaseRetriever):
    """Retriever for vector manager"""

    def __init__(self, vector_manager: VectorManager, store_type: VectorStoreType):
        super().__init__("VectorManager")
        self.vector_manager = vector_manager
        self.store_type = store_type

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Retrieve from vector manager"""
        try:
            # Search vector manager
            search_results = await self.vector_manager.search(
                request.query, top_k=request.max_results, store_type=self.store_type
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

            logger.info(
                f"Vector manager retrieved {len(results)} results for query: {request.query}")
            return results

        except Exception as e:
            logger.error(f"Vector manager retrieval failed: {e}")
            return []

    async def health_check(self) -> bool:
        """Check vector manager health"""
        try:
            # Try a simple search to verify connection
            await self.vector_manager.search("test", top_k=1)
            return True
        except Exception as e:
            logger.error(f"Vector manager health check failed: {e}")
            return False

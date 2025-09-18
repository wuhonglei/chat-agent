"""Retriever factory for creating and managing retrievers"""

from typing import Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.core.vector_store import VectorStore
from app.models.retrieval import RetrievalSource
from app.services.retrievers.base import BaseRetriever
from app.services.retrievers.vector_store_retriever import VectorStoreRetriever
from app.services.retrievers.web_search_retriever import WebSearchRetriever


class RetrieverFactory:
    """Factory for creating and managing retrievers"""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store
        self._retrievers: Dict[RetrievalSource, BaseRetriever] = {}
        self._init_retrievers()

    def _init_retrievers(self):
        """Initialize available retrievers"""
        try:
            # Vector store retriever
            if self.vector_store:
                self._retrievers[RetrievalSource.VECTOR_STORE] = VectorStoreRetriever(
                    self.vector_store
                )
                logger.info("Vector store retriever initialized")

            # Web search retriever
            if hasattr(settings, "TAVILY_API_KEY") and settings.TAVILY_API_KEY:
                self._retrievers[RetrievalSource.WEB_SEARCH] = WebSearchRetriever(
                    settings.TAVILY_API_KEY
                )
                logger.info("Web search retriever initialized")

            # TODO: Add other retrievers as they're implemented
            # - Confluence retriever
            # - Google Docs retriever
            # - PDF files retriever

        except Exception as e:
            logger.error(f"Failed to initialize retrievers: {e}")

    def get_retriever(self, source: RetrievalSource) -> Optional[BaseRetriever]:
        """Get retriever for a specific source"""
        return self._retrievers.get(source)

    def get_available_retrievers(self) -> List[RetrievalSource]:
        """Get list of available retrieval sources"""
        return list(self._retrievers.keys())

    def get_all_retrievers(self) -> Dict[RetrievalSource, BaseRetriever]:
        """Get all available retrievers"""
        return self._retrievers.copy()

    async def health_check(self) -> Dict[RetrievalSource, bool]:
        """Check health of all retrievers"""
        health_status = {}
        for source, retriever in self._retrievers.items():
            try:
                health_status[source] = await retriever.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {source}: {e}")
                health_status[source] = False
        return health_status

    def reload_retrievers(self):
        """Reload all retrievers (useful for config changes)"""
        self._retrievers.clear()
        self._init_retrievers()
        logger.info("Retrievers reloaded")
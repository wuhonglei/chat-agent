"""Retriever factory for creating and managing retrievers"""

from loguru import logger

from app.core.config import settings
from app.core.vector_store import VectorManager
from app.models.retrieval import RetrievalSource
from app.services.retrievers.base import BaseRetriever
from app.services.retrievers.confluence_retriever import ConfluenceRetriever
from app.services.retrievers.web_search_retriever import WebSearchRetriever


class RetrieverFactory:
    """Factory for creating and managing retrievers"""

    def __init__(self, vector_manager: VectorManager):
        self._retrievers: dict[RetrievalSource, BaseRetriever] = {}
        self.vector_manager = vector_manager
        self._init_retrievers()

    def _init_retrievers(self):
        """Initialize available retrievers"""
        try:
            if settings.CONFLUENCE_URL and settings.CONFLUENCE_PERSONAL_TOKEN:
                self._retrievers[RetrievalSource.CONFLUENCE] = ConfluenceRetriever(
                    api_config={
                        "url": settings.CONFLUENCE_URL,
                        "token": settings.CONFLUENCE_PERSONAL_TOKEN
                    }
                )
                logger.info("Confluence retriever initialized")

            # Web search retriever
            if settings.TAVILY_API_KEY:
                self._retrievers[RetrievalSource.WEB_SEARCH] = WebSearchRetriever(
                    settings.TAVILY_API_KEY
                )
                logger.info("Web search retriever initialized")

        except Exception as e:
            logger.error(f"Failed to initialize retrievers: {e}")

    def get_retriever(self, source: RetrievalSource) -> BaseRetriever | None:
        """Get retriever for a specific source"""
        return self._retrievers.get(source)

    def get_available_retrievers(self) -> list[RetrievalSource]:
        """Get list of available retrieval sources"""
        return list(self._retrievers.keys())

    def get_all_retrievers(self) -> dict[RetrievalSource, BaseRetriever]:
        """Get all available retrievers"""
        return self._retrievers.copy()

    async def health_check(self) -> dict[RetrievalSource, bool]:
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

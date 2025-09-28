"""Base class for vector store implementations"""

from abc import ABC, abstractmethod
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from loguru import logger

from app.core.config import settings
from app.models.document import Document, SearchResult


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations"""

    def __init__(self):
        self.embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
        )

    async def initialize_embeddings(self):
        """Initialize embeddings model"""
        try:
            self.embeddings = DashScopeEmbeddings(
                model=settings.EMBEDDING_MODEL,
                dashscope_api_key=settings.EMBEDDING_API_KEY,
            )
            logger.info("Embeddings model initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            raise

    @abstractmethod
    async def initialize(self):
        """Initialize the vector store"""
        pass

    @abstractmethod
    async def add_document(self, document: Document) -> list[str]:
        """Add document to vector store"""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = settings.SEARCH_TOP_K,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for relevant documents"""
        pass

    @abstractmethod
    async def delete_document(self, document_id: str):
        """Delete document from vector store"""
        pass

    @abstractmethod
    async def get_document_list(self) -> list[dict]:
        """Get list of all documents in the store"""
        pass

    @abstractmethod
    async def close(self):
        """Close vector store connections"""
        pass

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks using the configured text splitter"""
        return self.text_splitter.split_text(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        if not self.embeddings:
            raise RuntimeError("Embeddings model not initialized")
        return self.embeddings.embed_documents(texts)

    async def async_embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts asynchronously"""
        if not self.embeddings:
            raise RuntimeError("Embeddings model not initialized")
        return await self.embeddings.aembed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query"""
        if not self.embeddings:
            raise RuntimeError("Embeddings model not initialized")
        return self.embeddings.embed_query(query)

    async def async_embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query asynchronously"""
        if not self.embeddings:
            raise RuntimeError("Embeddings model not initialized")
        return await self.embeddings.aembed_query(query)

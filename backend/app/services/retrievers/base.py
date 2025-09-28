"""Base retriever interface"""

from abc import ABC, abstractmethod

from app.models.retrieval import RetrievalRequest, RetrievalResult


class BaseRetriever(ABC):
    """Abstract base class for all retrievers"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def initialize(self):
        """Initialize the retriever"""
        pass

    @abstractmethod
    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Retrieve relevant documents/content based on the request

        Args:
            request: Retrieval request containing query and parameters

        Returns:
            List of retrieval results

        Raises:
            Exception: If retrieval fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the retriever is healthy and available

        Returns:
            True if healthy, False otherwise
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

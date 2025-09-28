"""Vector Store Manager for handling different vector store implementations"""

from enum import Enum
from typing import Optional

from loguru import logger

from app.core.vector_store.base_vector_store import BaseVectorStore
from app.core.vector_store.memory_vector_store import MemoryVectorStore
from app.core.vector_store.persistent_vector_store import PersistentVectorStore


class VectorStoreType(Enum):
    """Enumeration of available vector store types"""

    MEMORY = "memory"
    PERSISTENT = "persistent"


class VectorManager:
    """Manages vector store instances and operations

    Usage:
        manager = VectorManager()
        await manager.initialize()

        # Direct access to stores
        await manager.memory.add_document(doc)
        await manager.persistent.search(query)
    """

    def __init__(self):
        self._stores: dict[str, BaseVectorStore] = {}
        self._default_store_type = VectorStoreType.PERSISTENT
        self._initialized = False
        self._memory_store: Optional[BaseVectorStore] = None
        self._persistent_store: Optional[BaseVectorStore] = None

    async def initialize(self):
        """Initialize the vector manager with both MEMORY and PERSISTENT stores"""
        if self._initialized:
            logger.warning("Vector manager already initialized")
            return

        # Initialize both vector store types
        for store_type in VectorStoreType:
            store = await self._get_or_create_store(store_type)
            # Set direct references for easy access
            if store_type == VectorStoreType.MEMORY:
                self._memory_store = store
            elif store_type == VectorStoreType.PERSISTENT:
                self._persistent_store = store

        self._initialized = True
        logger.info(
            f"Vector manager initialized with both MEMORY and PERSISTENT stores")
        logger.info(f"Default store type: {self._default_store_type.value}")

    async def _get_or_create_store(self, store_type: VectorStoreType) -> BaseVectorStore:
        """Get existing store or create a new one

        Args:
            store_type: Type of vector store to get or create

        Returns:
            Vector store instance
        """
        if store_type.value in self._stores:
            return self._stores[store_type.value]

        store = self._create_store(store_type)
        await store.initialize()
        self._stores[store_type.value] = store
        logger.info(f"Created and initialized {store_type.value} vector store")
        return store

    def _create_store(self, store_type: VectorStoreType) -> BaseVectorStore:
        """Factory method to create vector store instances

        Args:
            store_type: Type of vector store to create

        Returns:
            New vector store instance
        """
        if store_type == VectorStoreType.MEMORY:
            return MemoryVectorStore()
        elif store_type == VectorStoreType.PERSISTENT:
            return PersistentVectorStore()
        # This should never happen since we handle all enum values
        # but keeping it for type safety
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")

    async def close(self):
        """Close all vector store connections"""
        for store_name, store in self._stores.items():
            try:
                await store.close()
                logger.info(f"Closed {store_name} vector store")
            except Exception as e:
                logger.error(f"Error closing {store_name} store: {e}")

        self._stores.clear()
        self._initialized = False

    async def close_store(self, store_type: VectorStoreType):
        """Close a specific vector store

        Args:
            store_type: Store type to close
        """
        if store_type.value in self._stores:
            await self._stores[store_type.value].close()
            del self._stores[store_type.value]
            logger.info(f"Closed {store_type.value} vector store")

    def get_active_stores(self) -> list[str]:
        """Get list of currently active store types

        Returns:
            List of active store type names
        """
        return list(self._stores.keys())

    @property
    def default_store_type(self) -> VectorStoreType:
        """Get the current default store type"""
        return self._default_store_type

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized"""
        return self._initialized

    @property
    def memory(self) -> MemoryVectorStore:
        """Get the memory vector store instance

        Returns:
            Memory vector store instance

        Raises:
            RuntimeError: If manager is not initialized
        """
        if not self._initialized or not self._memory_store:
            raise RuntimeError(
                "Vector manager not initialized. Call initialize() first.")
        return self._memory_store

    @property
    def persistent(self) -> PersistentVectorStore:
        """Get the persistent vector store instance

        Returns:
            Persistent vector store instance

        Raises:
            RuntimeError: If manager is not initialized
        """
        if not self._initialized or not self._persistent_store:
            raise RuntimeError(
                "Vector manager not initialized. Call initialize() first.")
        return self._persistent_store


_vector_manager: Optional[VectorManager] = None


def get_vector_manager() -> VectorManager:
    """Get the global vector manager instance (singleton pattern)

    Returns:
        Global VectorManager instance
    """
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorManager()
    return _vector_manager


async def initialize_vector_manager():
    """Initialize the global vector manager with both MEMORY and PERSISTENT stores

    Returns:
        Initialized VectorManager instance
    """
    manager = get_vector_manager()
    await manager.initialize()
    return manager

"""Memory-based vector store implementation using Chroma"""

from typing import Optional

import chromadb
from loguru import logger

from app.core.vector_store.base_vector_store import BaseVectorStore
from app.core.config import settings
from app.models.document import Document, SearchResult


class MemoryVectorStore(BaseVectorStore):
    """Manages temporary vector storage in memory using Chroma"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.collection = None
        self.collection_name = "memory_collection"

    async def initialize(self):
        """Initialize vector store and embeddings"""
        try:
            # Initialize embeddings
            await self.initialize_embeddings()

            # Initialize Chroma client in memory mode
            self.client = chromadb.Client()

            # Create collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            logger.info("Memory vector store initialized")

        except Exception as e:
            logger.error(f"Failed to initialize memory vector store: {e}")
            raise

    async def add_document(self, document: Document) -> list[str]:
        """Add document to memory store"""
        try:
            # Split document into chunks
            chunks = self.split_text(document.content)

            # Generate embeddings
            embeddings = await self.async_embed_documents(chunks)

            # Prepare data for Chroma
            ids = [f"{document.id}_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "document_id": document.id,
                    "document_name": document.name,
                    "source": document.source,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                for i in range(len(chunks))
            ]

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )

            logger.info(
                f"Added document {document.name} with {len(chunks)} chunks to memory store"
            )
            return ids

        except Exception as e:
            logger.error(f"Failed to add document to memory store: {e}")
            raise

    async def batch_add_documents(self, documents: list[Document]) -> list[str]:
        """Batch add documents to memory store"""
        try:
            ids = []
            for document in documents:
                ids.extend(await self.add_document(document))
            return ids
        except Exception as e:
            logger.error(f"Failed to batch add documents to memory store: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int = settings.SEARCH_TOP_K,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for relevant documents in memory"""
        try:
            # Generate query embedding
            query_embedding = await self.async_embed_query(query)

            # Search in collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_dict,
            )

            # Format results
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    search_results.append(
                        SearchResult(
                            document_id=results["ids"][0][i],
                            document_name=results["metadatas"][0][i]["document_name"],
                            content=results["documents"][0][i],
                            metadata=results["metadatas"][0][i],
                            # Convert distance to similarity
                            score=1 - results["distances"][0][i],
                        )
                    )

            return search_results

        except Exception as e:
            logger.error(f"Search failed in memory store: {e}")
            raise

    async def delete_document(self, document_id: str):
        """Delete document from memory store"""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(where={"document_id": document_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} chunks for document {document_id} from memory store"
                )

        except Exception as e:
            logger.error(f"Failed to delete document from memory store: {e}")
            raise

    async def get_document_list(self) -> list[dict]:
        """Get list of all documents in the memory store"""
        try:
            # Get unique documents
            all_metadata = self.collection.get()["metadatas"]
            documents = {}

            for metadata in all_metadata:
                doc_id = metadata["document_id"]
                if doc_id not in documents:
                    documents[doc_id] = {
                        "id": doc_id,
                        "name": metadata["document_name"],
                        "source": metadata.get("source", "local"),
                        "chunks": 0,
                    }
                documents[doc_id]["chunks"] += 1

            return list(documents.values())

        except Exception as e:
            logger.error(f"Failed to get document list from memory store: {e}")
            raise

    async def close(self):
        """Clear memory store"""
        try:
            if self.client and self.collection:
                # Delete the collection to clear all data
                self.client.delete_collection(name=self.collection_name)
                logger.info("Memory vector store cleared and closed")
        except Exception as e:
            logger.warning(f"Error clearing memory store: {e}")

    def clear(self):
        """Clear all data from memory store by recreating the collection"""
        try:
            if self.client:
                # Delete and recreate the collection
                self.client.delete_collection(name=self.collection_name)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Memory vector store cleared")
        except Exception as e:
            logger.error(f"Failed to clear memory store: {e}")

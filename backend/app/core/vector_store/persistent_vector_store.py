"""Persistent vector store implementation using Chroma"""

import os
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.core.vector_store.base_vector_store import BaseVectorStore
from app.core.config import settings
from app.models.document import Document, SearchResult


class PersistentVectorStore(BaseVectorStore):
    """Manages persistent vector storage and retrieval using Chroma"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.collection = None
        self.collection_name = settings.CHROMA_COLLECTION_NAME

    async def initialize(self):
        """Initialize vector store and embeddings"""
        try:
            # Initialize embeddings
            await self.initialize_embeddings()

            # Initialize Chroma client
            os.makedirs(settings.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            logger.info(
                f"Persistent vector store initialized with {self.collection.count()} documents"
            )

        except Exception as e:
            logger.error(f"Failed to initialize persistent vector store: {e}")
            raise

    async def add_document(self, document: Document) -> list[str]:
        """Add document to vector store"""
        try:
            # Split document into chunks
            chunks = self.split_text(document.content)

            # Generate embeddings
            embeddings = self.embed_documents(chunks)

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
                f"Added document {document.name} with {len(chunks)} chunks to persistent store"
            )
            return ids

        except Exception as e:
            logger.error(f"Failed to add document to persistent store: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int = settings.SEARCH_TOP_K,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for relevant documents"""
        try:
            # Generate query embedding
            query_embedding = self.embed_query(query)

            # Search in collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_dict,
            )

            # Format results
            search_results = []
            for i in range(len(results["ids"][0])):
                search_results.append(
                    SearchResult(
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        # Convert distance to similarity
                        score=1 - results["distances"][0][i],
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Search failed in persistent store: {e}")
            raise

    async def delete_document(self, document_id: str):
        """Delete document from vector store"""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(where={"document_id": document_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} chunks for document {document_id} from persistent store"
                )

        except Exception as e:
            logger.error(
                f"Failed to delete document from persistent store: {e}")
            raise

    async def get_document_list(self) -> list[dict]:
        """Get list of all documents in the store"""
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
            logger.error(
                f"Failed to get document list from persistent store: {e}")
            raise

    async def close(self):
        """Close vector store connections"""
        logger.info("Persistent vector store closed")

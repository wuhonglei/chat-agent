"""Memory-based vector store implementation with direct embedding and ranking"""

from typing import Optional, List, Dict, Tuple
import numpy as np
from loguru import logger

from app.core.vector_store.base_vector_store import BaseVectorStore
from app.core.config import settings
from app.models.document import Document, SearchResult


class MemoryVectorStore(BaseVectorStore):
    """Manages temporary vector storage in memory with direct embedding and ranking"""

    def __init__(self):
        super().__init__()
        # Store documents and their embeddings in memory
        self.documents: Dict[str, Document] = {}
        # doc_id -> [(chunk_id, embedding, metadata)]
        self.embeddings: Dict[str, List[Tuple[str, List[float], Dict]]] = {}
        self.chunk_texts: Dict[str, str] = {}  # chunk_id -> chunk_text

    async def initialize(self):
        """Initialize vector store and embeddings"""
        try:
            # Initialize embeddings
            await self.initialize_embeddings()
            logger.info("Memory vector store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory vector store: {e}")
            raise

    async def add_document(self, document: Document) -> List[str]:
        """Add document to memory store
        Args:
            document: Document to add
        Returns:
            List of chunk IDs
        """
        try:
            # Store the document
            self.documents[document.id] = document

            # Split document into chunks
            chunks = self.split_text(document.content)

            # Enhance chunks with title for better semantic representation
            enhanced_chunks = []
            for chunk in chunks:
                # Format: "Title: [title]\n\nContent: [chunk]"
                enhanced_chunk = f"Title: {document.name}\n\nContent: {chunk}"
                enhanced_chunks.append(enhanced_chunk)

            # Generate embeddings
            embeddings = await self.async_embed_documents(enhanced_chunks)

            # Store embeddings with metadata
            chunk_data = []
            chunk_ids = []

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"{document.id}_{i}"
                metadata = {
                    "document_id": document.id,
                    "document_name": document.name,
                    "document_url": document.source_url,
                    "source": document.source,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }

                # Store chunk text (original, not enhanced)
                self.chunk_texts[chunk_id] = chunk

                # Store embedding data
                chunk_data.append((chunk_id, embedding, metadata))
                chunk_ids.append(chunk_id)

            # Store all chunk data for this document
            self.embeddings[document.id] = chunk_data

            logger.info(
                f"Added document {document.name} with {len(chunks)} chunks to memory store"
            )
            return chunk_ids

        except Exception as e:
            logger.error(f"Failed to add document to memory store: {e}")
            raise

    async def batch_add_documents(self, documents: List[Document]) -> List[str]:
        """Batch add documents to memory store"""
        try:
            all_ids = []
            for document in documents:
                ids = await self.add_document(document)
                all_ids.extend(ids)
            return all_ids
        except Exception as e:
            logger.error(f"Failed to batch add documents to memory store: {e}")
            raise

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def search(
        self,
        query: str,
        top_k: int = settings.SEARCH_TOP_K,
        filter_dict: Optional[dict] = None,
    ) -> List[SearchResult]:
        """Search for relevant documents in memory using cosine similarity"""
        try:
            # Generate query embedding
            query_embedding = await self.async_embed_query(query)

            # Calculate similarity scores for all chunks
            scored_chunks = []

            for doc_id, chunk_data_list in self.embeddings.items():
                for chunk_id, chunk_embedding, metadata in chunk_data_list:
                    # Apply filter if provided
                    if filter_dict:
                        match = all(
                            metadata.get(key) == value
                            for key, value in filter_dict.items()
                        )
                        if not match:
                            continue

                    # Calculate cosine similarity
                    similarity = self.cosine_similarity(
                        query_embedding, chunk_embedding)

                    # Get chunk text
                    chunk_text = self.chunk_texts.get(chunk_id, "")

                    scored_chunks.append({
                        "chunk_id": chunk_id,
                        "chunk_text": chunk_text,
                        "similarity": similarity,
                        "metadata": metadata
                    })

            # Sort by similarity (descending)
            scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)

            # Take top_k results
            top_chunks = scored_chunks[:top_k]

            # Format results
            search_results = []
            for chunk in top_chunks:
                search_results.append(
                    SearchResult(
                        document_id=chunk["chunk_id"],
                        document_name=chunk["metadata"]["document_name"],
                        content=chunk["chunk_text"],
                        metadata=chunk["metadata"],
                        score=chunk["similarity"]  # Cosine similarity score
                    )
                )

            logger.debug(
                f"Found {len(search_results)} results for query: {query[:50]}...")
            return search_results

        except Exception as e:
            logger.error(f"Search failed in memory store: {e}")
            raise

    async def delete_document(self, document_id: str):
        """Delete document from memory store"""
        try:
            # Remove document
            if document_id in self.documents:
                del self.documents[document_id]

            # Remove embeddings
            if document_id in self.embeddings:
                # Remove chunk texts
                for chunk_id, _, _ in self.embeddings[document_id]:
                    if chunk_id in self.chunk_texts:
                        del self.chunk_texts[chunk_id]

                # Remove embeddings
                del self.embeddings[document_id]

                logger.info(
                    f"Deleted document {document_id} from memory store")
            else:
                logger.warning(
                    f"Document {document_id} not found in memory store")

        except Exception as e:
            logger.error(f"Failed to delete document from memory store: {e}")
            raise

    async def get_document_list(self) -> List[dict]:
        """Get list of all documents in the memory store"""
        try:
            documents_info = []

            for doc_id, document in self.documents.items():
                chunk_count = len(self.embeddings.get(doc_id, []))
                documents_info.append({
                    "id": doc_id,
                    "name": document.name,
                    "source": document.source,
                    "chunks": chunk_count,
                    "url": document.source_url
                })

            return documents_info

        except Exception as e:
            logger.error(f"Failed to get document list from memory store: {e}")
            raise

    async def close(self):
        """Clear memory store"""
        try:
            self.documents.clear()
            self.embeddings.clear()
            self.chunk_texts.clear()
            logger.info("Memory vector store cleared and closed")
        except Exception as e:
            logger.warning(f"Error clearing memory store: {e}")

    def clear(self):
        """Clear all data from memory store"""
        try:
            self.documents.clear()
            self.embeddings.clear()
            self.chunk_texts.clear()
            logger.info("Memory vector store cleared")
        except Exception as e:
            logger.error(f"Failed to clear memory store: {e}")

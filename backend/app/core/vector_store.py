"""Vector store management for RAG"""

import os

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from loguru import logger

from app.core.config import settings
from app.models.document import Document, SearchResult


class VectorStore:
    """Manages vector storage and retrieval using Chroma"""

    def __init__(self):
        self.client = None
        self.collection = None
        self.embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
        )

    async def initialize(self):
        """Initialize vector store and embeddings"""
        try:
            # Initialize embeddings (using local model for MVP)
            self.embeddings = DashScopeEmbeddings(
                model=settings.EMBEDDING_MODEL,  # 或者使用 text-embedding-v2
                dashscope_api_key=settings.EMBEDDING_API_KEY,
            )

            # Initialize Chroma client
            os.makedirs(settings.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )

            logger.info(f"Vector store initialized with {self.collection.count()} documents")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    async def add_document(self, document: Document) -> list[str]:
        """Add document to vector store"""
        try:
            # Split document into chunks
            chunks = self.text_splitter.split_text(document.content)

            # Generate embeddings
            embeddings = self.embeddings.embed_documents(chunks)

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

            logger.info(f"Added document {document.name} with {len(chunks)} chunks")
            return ids

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int = settings.SEARCH_TOP_K,
        filter_dict: dict | None = None,
    ) -> list[SearchResult]:
        """Search for relevant documents"""
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)

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
            logger.error(f"Search failed: {e}")
            raise

    async def delete_document(self, document_id: str):
        """Delete document from vector store"""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(where={"document_id": document_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
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
            logger.error(f"Failed to get document list: {e}")
            raise

    async def close(self):
        """Close vector store connections"""
        logger.info("Vector store closed")

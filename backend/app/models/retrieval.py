"""Retrieval models and data structures"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievalSource(str, Enum):
    """Enumeration of retrieval sources"""

    KNOWLEDGE_BASE = "knowledge_base"
    WEB_SEARCH = "web_search"
    CONFLUENCE = "confluence"
    GOOGLE_DOCS = "google_docs"
    GOOGLE_SLIDES = "google_slides"
    PDF_FILES = "pdf_files"


class RetrievalMetadata(BaseModel):
    """Metadata for retrieval results"""

    # Common metadata
    document_id: Optional[str] = Field(
        None, description="Unique document identifier")
    document_url: Optional[str] = Field(
        None, description="Document source URL")
    favicon: Optional[str] = Field(None, description="Source favicon URL")

    # Confluence specific
    last_modified_time: Optional[str] = Field(
        None, description="Last modification time (ISO format)")
    last_modifier_name: Optional[str] = Field(
        None, description="Name of last modifier")
    last_modifier_id: Optional[str] = Field(
        None, description="ID of last modifier")

    # Web search specific
    search_engine: Optional[str] = Field(
        None, description="Search engine used (e.g., tavily, google)")
    published_date: Optional[str] = Field(
        None, description="Content publication date")
    raw_content: Optional[str] = Field(None, description="Raw HTML content")

    # Document specific
    file_type: Optional[str] = Field(
        None, description="File type (pdf, docx, etc.)")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    page_number: Optional[int] = Field(
        None, description="Page number in document")
    chunk_index: Optional[int] = Field(
        None, description="Chunk index in document")

    # Additional metadata
    type: Optional[str] = Field(
        None, description="Content type (answer, snippet, etc.)")
    language: Optional[str] = Field(None, description="Content language")
    author: Optional[str] = Field(None, description="Content author")
    tags: Optional[list[str]] = Field(None, description="Associated tags")

    # Allow additional fields for extensibility
    extra: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata fields")


class RetrievalResult(BaseModel):
    """Single retrieval result"""

    content: str
    title: str | None = None
    url: str | None = None
    source: RetrievalSource
    score: float = 0.0
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata as dictionary for backward compatibility")
    retrieved_at: datetime = Field(default_factory=datetime.now)

    def get_typed_metadata(self) -> RetrievalMetadata:
        """Get metadata as typed object"""
        return RetrievalMetadata(**self.metadata)


class RetrievalRequest(BaseModel):
    """Request for retrieval"""

    query: str
    sources: list[RetrievalSource] = Field(default_factory=list)
    max_results: int = 5
    min_score: float = 0.0
    metadata_filters: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    """Response from retrieval system"""

    results: list[RetrievalResult]
    query: str
    total_results: int
    sources_used: list[RetrievalSource]
    processing_time_ms: float
    timestamp: datetime = datetime.now()

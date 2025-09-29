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


class ConfluenceMetadata(BaseModel):
    """Metadata specific to Confluence retrieval"""

    last_modified_time: Optional[str] = Field(
        None, description="Last modification time (ISO format)")
    last_modifier_name: Optional[str] = Field(
        None, description="Name of last modifier")
    last_modifier_id: Optional[str] = Field(
        None, description="ID of last modifier (accountId or userKey)")
    document_id: Optional[str] = Field(
        None, description="Unique document identifier")
    snippet: Optional[str] = Field(
        None, description="Snippet of the document")


class WebSearchMetadata(BaseModel):
    """Metadata specific to web search retrieval"""
    favicon: Optional[str] = Field(None, description="Source favicon URL")
    search_engine: str = Field(...,
                               description="Search engine used (e.g., tavily, google)")
    type: Optional[str] = Field(
        None, description="Content type (answer, snippet, article, etc.)")


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

    def get_confluence_metadata(self) -> ConfluenceMetadata:
        """Get metadata as Confluence-specific typed object"""
        return ConfluenceMetadata(**self.metadata)

    def get_web_search_metadata(self) -> WebSearchMetadata:
        """Get metadata as WebSearch-specific typed object"""
        return WebSearchMetadata(**self.metadata)


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

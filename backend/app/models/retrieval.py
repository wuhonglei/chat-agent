"""Retrieval models and data structures"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class RetrievalSource(str, Enum):
    """Enumeration of retrieval sources"""

    VECTOR_STORE = "vector_store"
    WEB_SEARCH = "web_search"
    CONFLUENCE = "confluence"
    GOOGLE_DOCS = "google_docs"
    GOOGLE_SLIDES = "google_slides"
    PDF_FILES = "pdf_files"


class RetrievalResult(BaseModel):
    """Single retrieval result"""

    content: str
    title: str | None = None
    url: str | None = None
    source: RetrievalSource
    score: float = 0.0
    metadata: dict[str, Any] = {}
    retrieved_at: datetime = datetime.now()


class RetrievalRequest(BaseModel):
    """Request for retrieval"""

    query: str
    sources: list[RetrievalSource] = [RetrievalSource.VECTOR_STORE]
    max_results: int = 5
    min_score: float = 0.0
    metadata_filters: dict[str, Any] = {}


class RetrievalResponse(BaseModel):
    """Response from retrieval system"""

    results: list[RetrievalResult]
    query: str
    total_results: int
    sources_used: list[RetrievalSource]
    processing_time_ms: float
    timestamp: datetime = datetime.now()

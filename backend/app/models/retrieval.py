"""Retrieval models and data structures"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
    title: Optional[str] = None
    url: Optional[str] = None
    source: RetrievalSource
    score: float = 0.0
    metadata: Dict[str, Any] = {}
    retrieved_at: datetime = datetime.now()


class RetrievalRequest(BaseModel):
    """Request for retrieval"""

    query: str
    sources: List[RetrievalSource] = [RetrievalSource.VECTOR_STORE]
    max_results: int = 5
    min_score: float = 0.0
    metadata_filters: Dict[str, Any] = {}


class RetrievalResponse(BaseModel):
    """Response from retrieval system"""

    results: List[RetrievalResult]
    query: str
    total_results: int
    sources_used: List[RetrievalSource]
    processing_time_ms: float
    timestamp: datetime = datetime.now()
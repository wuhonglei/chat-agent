"""Document models"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentSource(str, Enum):
    """Document source types"""

    LOCAL = "local"
    CONFLUENCE = "confluence"
    GOOGLE_DOCS = "google_docs"
    GOOGLE_SLIDES = "google_slides"


class DocumentStatus(str, Enum):
    """Document processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    """Document model"""

    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    source: DocumentSource = Field(
        DocumentSource.LOCAL, description="Document source")
    source_url: Optional[str] = Field(
        None, description="Source URL for external documents")
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Document metadata")
    status: DocumentStatus = Field(
        DocumentStatus.PENDING, description="Processing status")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Update timestamp")
    chunk_count: int = Field(0, description="Number of chunks")

    class Config:
        use_enum_values = True


class DocumentUpload(BaseModel):
    """Document upload request"""

    name: str = Field(..., description="Document name")
    content: Optional[str] = Field(
        None, description="Document content (for text uploads)")
    source_url: Optional[str] = Field(
        None, description="External document URL")
    source: DocumentSource = Field(
        DocumentSource.LOCAL, description="Document source")


class DocumentResponse(BaseModel):
    """Document response"""

    id: str
    name: str
    source: str
    source_url: Optional[str]
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    """Search result model"""

    content: str = Field(..., description="Content chunk")
    metadata: Dict[str, Any] = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Relevance score")
    document_id: Optional[str] = Field(None, description="Source document ID")
    document_name: Optional[str] = Field(
        None, description="Source document name")

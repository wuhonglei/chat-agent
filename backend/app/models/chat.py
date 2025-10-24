"""Chat models"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    """Source configuration model"""

    web_search: bool = Field(False, description="Whether to use web search")
    confluence: bool = Field(False, description="Whether to use confluence")
    google_docs: bool = Field(False, description="Whether to use google docs")
    knowledge_base: bool = Field(
        False, description="Whether to use knowledge base")


class ChatMessage(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata")


class ChatRequest(BaseModel):
    """Chat request model"""

    message: str = Field(..., description="User message")
    session_id: str | None = Field(None, description="Session ID for context")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Chat history")
    source_config: SourceConfig = Field(
        default_factory=SourceConfig, description="Source configuration"
    )
    mcp_auto_mode: bool = Field(
        True, description="Whether to use mcp auto mode")
    think_mode: bool = Field(False, description="Whether to use think mode")


class ChatSource(BaseModel):
    """Chat source reference model"""

    content: str = Field(..., description="Source content snippet")
    title: str = Field(..., description="Source title")
    url: Optional[str] = Field(None, description="Source URL")
    source: str = Field(...,
                        description="Source type (e.g., confluence, web, google_docs)")
    score: float = Field(..., description="Relevance score")
    favicon: Optional[str] = Field(
        None, description="Web search source favicon")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (last_modified_time, last_modifier_name, etc.)"
    )


class ChatResponse(BaseModel):
    """Chat response model"""

    message: str = Field(..., description="Assistant response")
    sources: list[ChatSource] = Field(
        default_factory=list, description="Source documents")
    session_id: str = Field(..., description="Session ID")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp")


class ChatSession(BaseModel):
    """Chat session model"""

    id: str = Field(..., description="Session ID")
    messages: list[ChatMessage] = Field(
        default_factory=list, description="Session messages")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Session creation time")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Session metadata")

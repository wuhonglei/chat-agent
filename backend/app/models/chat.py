"""Chat models"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model"""

    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata")


class ChatRequest(BaseModel):
    """Chat request model"""

    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(
        None, description="Session ID for context")
    history: List[ChatMessage] = Field(
        default_factory=list, description="Chat history")
    use_knowledge_base: bool = Field(
        True, description="Whether to use knowledge base")
    think_mode: bool = Field(False, description="Whether to use think mode")
    stream: bool = Field(False, description="Whether to stream response")


class ChatResponse(BaseModel):
    """Chat response model"""

    message: str = Field(..., description="Assistant response")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list, description="Source documents")
    session_id: str = Field(..., description="Session ID")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp")


class ChatSession(BaseModel):
    """Chat session model"""

    id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(
        default_factory=list, description="Session messages")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Session creation time")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update time")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Session metadata")

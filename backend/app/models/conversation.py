"""Conversation models for FastAPI"""

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from app.models.chat import ChatMessage


class ConversationInfo(BaseModel):
    """Conversation information model"""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Update timestamp (ISO format)")
    message_count: int = Field(...,
                               description="Number of messages in the conversation")

    # 允许额外字段
    model_config = ConfigDict(extra="allow")


class RegisterConversationRequest(BaseModel):
    """Register conversation request model"""
    title: Optional[str] = Field(None, description="Conversation title")


class ConversationListResponse(BaseModel):
    """Conversation list response model"""
    total: int = Field(..., description="Total number of conversations")
    offset: int = Field(..., description="Offset for pagination")
    limit: int = Field(..., description="Limit for pagination")
    conversations: list[ConversationInfo] = Field(
        ..., description="List of conversations")


class ConversationDetailResponse(ConversationInfo):
    """Conversation detail response model"""
    messages: list[ChatMessage] = Field(...,
                                        description="List of messages in the conversation")


class UpdateConversationRequest(BaseModel):
    """Update conversation request model"""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="New conversation title")

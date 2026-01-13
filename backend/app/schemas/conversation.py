"""Conversation models for FastAPI"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatMessageItemReq


class CreatedBy(str, Enum):
    """标题创建方式枚举"""

    DEFAULT = "default"
    USER = "user"
    LLM = "llm"


class ConversationInfo(BaseModel):
    """Conversation information model"""

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_by: CreatedBy = Field(..., description="Conversation created by")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Update timestamp (ISO format)")

    # 允许额外字段
    model_config = ConfigDict(extra="allow")


class RegisterConversationRequest(BaseModel):
    """Register conversation request model"""

    title: str | None = Field(None, description="Conversation title")


class ConversationListResponse(BaseModel):
    """Conversation list response model"""

    total: int = Field(..., description="Total number of conversations")
    offset: int = Field(..., description="Offset for pagination")
    limit: int = Field(..., description="Limit for pagination")
    conversations: list[ConversationInfo] = Field(
        ..., description="List of conversations"
    )


class ConversationDetailResponse(ConversationInfo):
    """Conversation detail response model"""

    messages: list[ChatMessageItemReq] = Field(
        ..., description="List of messages in the conversation"
    )


class UpdateConversationRequest(BaseModel):
    """Update conversation request model"""

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="New conversation title")
    created_by: CreatedBy = Field(..., description="Conversation created by")

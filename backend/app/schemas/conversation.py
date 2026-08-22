"""Conversation models for FastAPI"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatMessageRequestItem


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
    is_active: bool = Field(default=True, description="Whether conversation is visible")


class ConversationListRequest(BaseModel):
    """对话列表查询请求（游标分页）"""

    cursor: str | None = Field(None, description="游标，首页不传")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class ConversationListResponse(BaseModel):
    """Conversation list response model"""

    conversations: list[ConversationInfo] = Field(
        ..., description="List of conversations"
    )
    next_cursor: str | None = Field(None, description="下一页游标，末页为 null")
    has_more: bool = Field(..., description="是否还有更多数据")
    limit: int = Field(..., description="本页 limit")


class ConversationDetailResponse(ConversationInfo):
    """Conversation detail response model"""

    messages: list[ChatMessageRequestItem] = Field(
        ..., description="List of messages in the conversation"
    )


class UpdateConversationRequest(BaseModel):
    """Update conversation request model"""

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="New conversation title")
    created_by: CreatedBy = Field(..., description="Conversation created by")


class ConversationSearchMatchType(str, Enum):
    """搜索命中类型"""

    TITLE = "title"
    USER = "user"
    ASSISTANT = "assistant"


class ConversationSearchRequest(BaseModel):
    """会话搜索请求（游标分页）"""

    q: str = Field(..., min_length=1, max_length=200, description="搜索关键词")
    cursor: str | None = Field(None, description="游标，首页不传")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class ConversationSearchItem(BaseModel):
    """单条会话搜索结果"""

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    match_type: ConversationSearchMatchType = Field(
        ..., description="命中类型：title / user / assistant"
    )
    snippet: str = Field("", description="命中片段（title 命中可为空）")
    updated_at: str = Field(
        ..., description="用于展示的时间（优先 last_message_created_at）"
    )


class ConversationSearchResponse(BaseModel):
    """会话搜索响应"""

    conversations: list[ConversationSearchItem] = Field(..., description="搜索结果列表")
    next_cursor: str | None = Field(None, description="下一页游标，末页为 null")
    has_more: bool = Field(..., description="是否还有更多数据")
    limit: int = Field(..., description="本页 limit")


class ConversationCompressResponse(BaseModel):
    """会话手动全量压缩结果"""

    summary: str = Field(..., description="压缩后的摘要正文")
    tokens_before: int = Field(..., description="压缩前（摘要输入文本）token 数")
    tokens_after: int = Field(..., description="压缩后摘要 token 数")
    summarized_message_count: int = Field(..., description="被纳入压缩的消息条数")

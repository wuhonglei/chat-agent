from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model"""

    id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    email: str | None = Field(None, description="User email")
    avatar: str | None = Field(None, description="User avatar")
    phone: str | None = Field(None, description="User phone")
    sub: str | None = Field(None, description="User ID in the cloudbase")
    last_login_at: datetime | None = Field(None, description="Last login at")
    last_logout_at: datetime | None = Field(None, description="Last logout at")
    last_login_type: str | None = Field("sms", description="Last login type")
    role: str = Field("user", description="User role")
    status: str = Field("active", description="User status")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class UpdateUserInfo(BaseModel):
    name: str | None = Field(None, description="User name")
    avatar: str | None = Field(None, description="User avatar")


class MemoryListItem(BaseModel):
    """Mem0 记忆单条（与 Mem0 GET /memories 对齐）"""

    id: str = Field(..., description="记忆 ID")
    memory: str = Field("", description="记忆内容")
    hash: str | None = Field(None, description="hash")
    created_at: str | None = Field(None, description="创建时间")
    metadata: dict[str, Any] | None = Field(None, description="元数据")
    score: float = Field(..., description="相关性分数（搜索时）")


class MemoryListResponse(BaseModel):
    """用户记忆列表响应（Mem0 GET /memories 映射）"""

    memories: list[MemoryListItem] = Field(default_factory=list, description="记忆列表")

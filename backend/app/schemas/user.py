from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# 与 mem0 `governance_filters` 对齐：缺省 status 视为 active，缺省 kind 为普通记忆。
MemoryGovernanceStatus = Literal["active", "merged", "superseded", "archived"]
MemoryKind = Literal["pattern"]
MemoryRole = Literal["user", "assistant"]


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
    """Mem0 记忆单条（与 OSS get/search 提升到顶层的字段对齐）。"""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="记忆 ID")
    memory: str = Field("", description="记忆内容")
    hash: str | None = Field(None, description="内容 hash")
    metadata: dict[str, Any] | None = Field(None, description="额外元数据")
    created_at: str = Field(..., description="创建时间(ISO 8601)")
    updated_at: str | None = Field(None, description="更新时间(ISO 8601)")
    user_id: str | None = Field(None, description="所属用户 ID")
    role: MemoryRole | None = Field(None, description="来源角色：user / assistant")
    score: float | None = Field(None, description="相关性分数（搜索时）")
    governance_status: MemoryGovernanceStatus | None = Field(
        None, description="治理状态；缺省视为 active"
    )
    memory_kind: MemoryKind | None = Field(
        None, description="记忆类型；pattern 为治理合成，缺省为普通记忆"
    )
    synthesized_from: list[str] | None = Field(
        None, description="合成该条记忆的来源 ID"
    )
    governance_pass_id: str | None = Field(None, description="治理 pass ID")
    governance_timestamp: str | None = Field(None, description="治理时间(ISO 8601)")
    synthesis_evidence_hash: str | None = Field(None, description="合成证据 hash")
    merged_into: str | None = Field(None, description="merged 时指向的规范记忆 ID")
    superseded_by: str | None = Field(None, description="superseded 时指向的新记忆 ID")


class MemorySearchItem(BaseModel):
    """用户记忆搜索结果（用于对话上下文注入）。"""

    id: str = Field(..., description="记忆 ID")
    memory: str = Field("", description="记忆内容")
    hash: str | None = Field(default=None, description="hash")
    created_at: str | None = Field(default=None, description="创建时间（相对时间）")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    relevance: Literal["高", "中", "低"] = Field(..., description="相关度等级")
    governance_status: MemoryGovernanceStatus = Field(
        "active", description="治理状态；缺省视为 active"
    )


class MemoryListResponse(BaseModel):
    """用户记忆列表响应（Mem0 GET /memories 映射）"""

    memories: list[MemoryListItem] = Field(default_factory=list, description="记忆列表")

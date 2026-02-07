from datetime import datetime

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
    name: str = Field(..., description="User name")
    avatar: str | None = Field(None, description="User avatar")


class UserProfileItem(BaseModel):
    """用户画像单条：事实或偏好"""

    id: str = Field(..., description="条目 ID")
    text: str = Field(..., description="内容")
    type: str = Field(..., description="fact | preference")
    created_at: datetime = Field(..., description="创建时间")


class UserProfileList(BaseModel):
    """用户画像列表：facts 与 preferences"""

    facts: list[UserProfileItem] = Field(default_factory=list, description="事实列表")
    preferences: list[UserProfileItem] = Field(
        default_factory=list, description="偏好列表"
    )

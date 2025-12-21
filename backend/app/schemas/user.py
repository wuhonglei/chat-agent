from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class User(BaseModel):
    """User model"""

    id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    email: Optional[str] = Field(None, description="User email")
    avatar: Optional[str] = Field(None, description="User avatar")
    phone: Optional[str] = Field(None, description="User phone")
    sub: Optional[str] = Field(None, description="User ID in the cloudbase")
    last_login_at: Optional[datetime] = Field(
        None, description="Last login at")
    last_logout_at: Optional[datetime] = Field(
        None, description="Last logout at")
    last_login_type: Optional[str] = Field(
        "sms", description="Last login type")
    role: str = Field("user", description="User role")
    status: str = Field("active", description="User status")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class UpdateUserInfo(BaseModel):
    name: str = Field(..., description="User name")
    avatar: Optional[str] = Field(None, description="User avatar")

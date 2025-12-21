from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field

from app.utils.date import get_datetime_now
from app.utils.common import gen_uuid


class UserDb(SQLModel, table=True):
    """用户模型"""
    __tablename__ = "users"

    id: str = Field(default_factory=gen_uuid, primary_key=True,
                    index=True, max_length=36)
    name: str = Field(..., description="User name")
    email: Optional[str] = Field(unique=True, index=True)
    avatar: Optional[str] = None
    phone: Optional[str] = Field(unique=True, index=True)
    sub: Optional[str] = Field(
        unique=True, index=True, description="User ID in the cloudbase")
    last_login_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True))
    last_logout_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True))
    last_login_type: Optional[str] = Field(
        default="sms", description="Last login type")
    role: str = Field(default="user")
    status: str = Field(default="active or inactive",
                        description="User status")
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True)
    )

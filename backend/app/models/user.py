from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class UserDb(SQLModel, table=True):
    """用户模型"""

    __tablename__ = "users"

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    name: str = Field(..., description="User name")
    email: str | None = Field(default=None, unique=True, index=True)
    avatar: str | None = None
    phone: str | None = Field(default=None, unique=True, index=True)
    sub: str | None = Field(
        default=None,
        unique=True,
        index=True,
        description="User ID in the cloudbase",
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_logout_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_login_type: str | None = Field(default="sms", description="Last login type")
    role: str = Field(default="user")
    status: str = Field(default="active or inactive", description="User status")
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=get_datetime_now,
        ),
    )

"""Published static sites served at ``{slug}.{public_base_domain}``."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Text
from sqlmodel import Field, SQLModel

from app.utils.date import get_datetime_now


class PublishedSite(SQLModel, table=True):
    """One published site per conversation; slug is the public DNS label."""

    __tablename__ = "published_sites"  # pyright: ignore[reportAssignmentType]

    slug: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(
        ...,
        index=True,
        max_length=36,
        foreign_key="users.id",
        description="站点所属用户",
    )
    conversation_id: str = Field(
        ...,
        unique=True,
        max_length=36,
        foreign_key="conversations.id",
        description="一会话一站；重复发布升 version，不换 slug",
    )
    message_id: str | None = Field(
        default=None,
        max_length=36,
        description="溯源：哪条消息触发的发布",
    )
    site_root: str = Field(
        sa_column=Column(Text, nullable=False),
        description="快照绝对路径，仅服务端生成",
    )
    version: int = Field(default=1)
    entry: str = Field(default="index.html", max_length=128)
    visibility: str = Field(default="unlisted", max_length=16)
    size_bytes: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    unpublished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

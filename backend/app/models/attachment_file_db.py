from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class AttachmentFileDb(SQLModel, table=True):
    """聊天附件文件实体索引。"""

    __tablename__ = "attachment_files"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "storage_key",
            name="uq_attachment_files_user_storage_key",
        ),
    )

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    user_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="所属用户",
    )
    content_id: str = Field(
        sa_column=Column(String(64), nullable=False, index=True),
        description="附件块 id / 内容 ID",
    )
    storage_key: str = Field(
        sa_column=Column(String(256), nullable=False),
        description="相对 shared/uploads 的存储 key",
    )
    kind: str = Field(sa_column=Column(String(32), nullable=False))
    mime: str = Field(sa_column=Column(String(128), nullable=False))
    size: int = Field(default=0, ge=0)
    display_name: str = Field(default="", max_length=240)
    derived_from_id: str | None = Field(default=None, max_length=64)
    derived_kind: str | None = Field(default=None, max_length=64)
    legacy_source: str | None = Field(default=None, max_length=512)
    storage_version: int = Field(default=2)
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=get_datetime_now,
        ),
    )

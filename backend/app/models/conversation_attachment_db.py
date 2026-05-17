from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class ConversationAttachmentDb(SQLModel, table=True):
    """会话与聊天附件的挂载关系。"""

    __tablename__ = "conversation_attachments"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "storage_key",
            name="uq_conversation_attachments_conversation_storage_key",
        ),
    )

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    conversation_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    user_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    attachment_file_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("attachment_files.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    storage_key: str = Field(sa_column=Column(String(256), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

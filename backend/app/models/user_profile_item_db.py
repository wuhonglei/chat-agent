"""用户画像条目：单条事实/偏好 + pgvector embedding_vector"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, SmallInteger, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.config import settings
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class UserProfileItemDb(SQLModel, table=True):
    """用户画像条目：单条事实或偏好，带语义向量"""

    __tablename__ = "user_profile_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "text_normalized_hash",
            "type",
            name="uq_user_profile_items_user_text_type",
        ),
        Index("ix_user_profile_items_user_deleted", "user_id", "deleted_at"),
    )

    id: str = Field(
        default_factory=gen_uuid,
        primary_key=True,
        index=True,
        max_length=36,
    )
    user_id: str = Field(
        index=True,
        max_length=36,
        foreign_key="users.id",
        description="用户 ID",
    )
    text: str = Field(sa_type=Text, description="单条事实或偏好内容")
    type: int = Field(
        sa_type=SmallInteger,
        description="1=事实(fact)，2=偏好(preference)",
    )
    embedding_vector: list[float] | None = Field(
        default=None,
        sa_type=Vector(settings.embedding_model.embedding_dimension),
        description="语义向量",
    )
    embedding_model: str | None = Field(
        default=None,
        max_length=50,
        description="向量对应模型版本，检索时只使用与当前配置一致的数据",
    )
    text_normalized_hash: str = Field(
        max_length=64,
        description="归一化 text 的 hash，用于唯一约束",
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="软删除时间，有值表示已删除",
    )
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True),
    )

"""用户级画像：跨会话复用的事实与偏好"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.core.db import JSONUTF8
from app.utils.date import get_datetime_now


class UserProfileDb(SQLModel, table=True):
    """用户级画像：跨会话复用的事实与偏好"""

    __tablename__ = "user_profiles"

    user_id: str = Field(
        primary_key=True,
        index=True,
        max_length=36,
        description="用户 ID，与 users.id 对应",
    )
    facts: list[str] | None = Field(
        default=None,
        sa_type=JSONUTF8(),
        description="从多轮对话提炼的可信事实，如「在北京工作」「用 Python 3.10」",
    )
    preferences: list[str] | None = Field(
        default=None,
        sa_type=JSONUTF8(),
        description="用户偏好，如「偏好简短回答」「不要用代码块」",
    )
    updated_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column_kwargs={"onupdate": get_datetime_now},
        sa_type=DateTime(timezone=True),
    )

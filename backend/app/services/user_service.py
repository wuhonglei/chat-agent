from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select, delete

from app.models.chat import ChatMessageItemReq, MessageStatus
from app.models.db import Conversation, Message, User
from app.utils.common import get_datetime_now
from app.core.db import engine


class UserService:
    """User service"""

    def __init__(self):
        pass

    def __enter__(self):
        self.db: Optional[Session] = Session(engine)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.db:
            self.db.close()
            self.db = None

    def get_user(self, user_id: str) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def create_user(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

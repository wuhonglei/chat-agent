from __future__ import annotations

import string
from typing import Optional

from sqlmodel import Session, select

from app.models.auth import VerifySmsResponse
from app.models.db import UserDb
from app.models.user import UpdateUserInfo
from app.utils.date import get_datetime_now
from app.core.db import engine


class UserService:
    """User service"""

    def __init__(self, db: Optional[Session]):
        self.db = db

    def __enter__(self):
        self.db: Optional[Session] = Session(engine)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.db:
            self.db.close()
            self.db = None

    def get_user(self, user_id: str) -> UserDb:
        user = self.db.get(UserDb, user_id)
        return user

    def create_user(self, user: UserDb) -> UserDb:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_sub(self, sub: str) -> UserDb:
        user = self.db.exec(select(UserDb).where(UserDb.sub == sub)).first()
        return user

    def create_user_from_cloudbase(self, token_info: VerifySmsResponse, phone_number: string) -> UserDb:
        user = UserDb(
            sub=token_info.sub,
            last_login_at=get_datetime_now(),
            last_login_type="sms",
            status="active",
            phone=phone_number,
            name=phone_number.split(" ")[-1] or phone_number,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_last_login(self, user: UserDb, last_login_type: str) -> UserDb:
        user.last_login_at = get_datetime_now()
        user.last_login_type = last_login_type
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_last_logout(self, user_id: str) -> None:
        user = self.get_user(user_id)
        if user:
            user.last_logout_at = get_datetime_now()
            user.status = "inactive"
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

    def update_user_info(self, user_id: str, update_info: UpdateUserInfo) -> UserDb:
        user = self.get_user(user_id)
        if user:
            user.name = update_info.name
            user.avatar = update_info.avatar
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

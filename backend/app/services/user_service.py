from __future__ import annotations

import string
from typing import Optional

from sqlmodel import Session, select

from app.models.auth import VerifySmsResponse
from app.models.db import UserDb
from app.models.user import UpdateUserInfo
from app.utils.date import get_datetime_now
from app.services.base_service import BaseService


class UserService(BaseService):
    """用户服务"""

    def __init__(self, db: Optional[Session] = None):
        """
        初始化用户服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        super().__init__(db)

    def get_user(self, user_id: str) -> UserDb:
        """获取用户"""
        db = self._ensure_db()
        user = db.get(UserDb, user_id)
        return user

    def create_user(self, user: UserDb) -> UserDb:
        """创建用户"""
        db = self._ensure_db()
        db.add(user)
        # 所有字段都有 default_factory 或手动设置，不需要 refresh()
        # 事务由 get_db() 或 BaseService.__exit__ 自动提交
        return user

    def get_user_by_sub(self, sub: str) -> UserDb:
        """通过 sub 获取用户"""
        db = self._ensure_db()
        user = db.exec(select(UserDb).where(UserDb.sub == sub)).first()
        return user

    def create_user_from_cloudbase(self, token_info: VerifySmsResponse, phone_number: string) -> UserDb:
        """从 Cloudbase 创建用户"""
        db = self._ensure_db()
        user = UserDb(
            sub=token_info.sub,
            last_login_at=get_datetime_now(),
            last_login_type="sms",
            status="active",
            phone=phone_number,
            name=phone_number.split(" ")[-1] or phone_number,
        )
        db.add(user)
        # 所有字段都有 default_factory 或手动设置，不需要 refresh()
        # 事务由 get_db() 或 BaseService.__exit__ 自动提交
        return user

    def update_user_last_login(self, user: UserDb, last_login_type: str) -> UserDb:
        """更新用户最后登录时间"""
        db = self._ensure_db()
        user.last_login_at = get_datetime_now()
        user.last_login_type = last_login_type
        db.add(user)
        # updated_at 通过 onupdate 在 Python 层面自动更新，不需要 refresh()
        # 事务由 get_db() 或 BaseService.__exit__ 自动提交
        return user

    def update_user_last_logout(self, user_id: str) -> None:
        """更新用户最后登出时间"""
        db = self._ensure_db()
        user = self.get_user(user_id)
        if user:
            user.last_logout_at = get_datetime_now()
            user.status = "inactive"
            db.add(user)
            # updated_at 通过 onupdate 在 Python 层面自动更新，不需要 refresh()
            # 事务由 get_db() 或 BaseService.__exit__ 自动提交

    def update_user_info(self, user_id: str, update_info: UpdateUserInfo) -> UserDb:
        """更新用户信息"""
        db = self._ensure_db()
        user = self.get_user(user_id)
        if user:
            user.name = update_info.name
            user.avatar = update_info.avatar
            db.add(user)
            # updated_at 通过 onupdate 在 Python 层面自动更新，不需要 refresh()
            # 事务由 get_db() 或 BaseService.__exit__ 自动提交
        return user

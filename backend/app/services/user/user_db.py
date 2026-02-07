from __future__ import annotations

from sqlmodel import Session, select

from app.models import UserDb
from app.schemas.auth import SigninResponse, WeChatUserInfoResponse
from app.schemas.user import UpdateUserInfo
from app.services.base_service.db_service import DbService
from app.utils.date import get_datetime_now
from app.utils.logger import logger


class UserDbService(DbService):
    """用户 DB 服务"""

    def __init__(self, db: Session | None = None):
        """
        初始化用户 DB 服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        super().__init__(db)

    def get_user(self, user_id: str) -> UserDb | None:
        """获取用户"""
        db = self._ensure_db()
        user = db.get(UserDb, user_id)
        return user

    def create_user(self, user: UserDb) -> UserDb:
        """创建用户"""
        db = self._ensure_db()
        db.add(user)
        # 所有字段都有 default_factory 或手动设置，不需要 refresh()
        # 事务由 get_db() 或 DbService.__exit__ 自动提交
        return user

    def get_user_by_sub(self, sub: str) -> UserDb | None:
        """通过 sub 获取用户"""
        db = self._ensure_db()
        user = db.exec(select(UserDb).where(UserDb.sub == sub)).first()
        return user

    def get_user_by_phone(self, phone: str) -> UserDb | None:
        """通过手机号获取用户"""
        db = self._ensure_db()
        user = db.exec(select(UserDb).where(UserDb.phone == phone)).first()
        return user

    def get_or_create_user_by_phone(self, phone: str) -> UserDb:
        """根据手机号查找或创建用户（短信登录用，sub 使用 sms:{phone}）"""
        db = self._ensure_db()
        user = self.get_user_by_phone(phone)
        sub = f"sms:{phone}"
        if not user:
            user = UserDb(
                sub=sub,
                phone=phone,
                name=phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone,
                last_login_at=get_datetime_now(),
                last_login_type="sms",
                status="active",
            )
            db.add(user)
            logger.info("创建短信用户", phone=phone, user_id=user.id)
        else:
            user.last_login_at = get_datetime_now()
            user.last_login_type = "sms"
            db.add(user)
            logger.info("更新短信用户登录信息", phone=phone, user_id=user.id)
        return user

    def create_user_from_cloudbase(
        self, token_info: SigninResponse, phone_number: str
    ) -> UserDb:
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
        # 事务由 get_db() 或 DbService.__exit__ 自动提交
        return user

    def update_user_last_login(self, user: UserDb, last_login_type: str) -> UserDb:
        """更新用户最后登录时间"""
        db = self._ensure_db()
        user.last_login_at = get_datetime_now()
        user.last_login_type = last_login_type
        db.add(user)
        # updated_at 通过 onupdate 在 Python 层面自动更新，不需要 refresh()
        # 事务由 get_db() 或 DbService.__exit__ 自动提交
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
            # 事务由 get_db() 自动提交

    def update_user_info(self, user_id: str, update_info: UpdateUserInfo) -> UserDb:
        """更新用户信息"""
        db = self._ensure_db()
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"用户不存在: {user_id}")
        if update_info.name is not None:
            user.name = update_info.name
        if update_info.avatar is not None:
            user.avatar = update_info.avatar
        db.add(user)
        return user

    def get_or_create_user_by_openid(
        self, openid: str, wechat_user_info: WeChatUserInfoResponse
    ) -> UserDb:
        """根据 openid 查找或创建用户（使用 sub 字段存储 openid）

        Args:
            openid: 微信用户的 openid
            wechat_user_info: 微信用户信息字典

        Returns:
            用户对象
        """
        db = self._ensure_db()
        # 使用 sub 字段存储 openid
        user = self.get_user_by_sub(openid)

        if not user:
            # 创建新用户
            nickname = wechat_user_info.nickname
            avatar = wechat_user_info.headimgurl
            user = UserDb(
                sub=openid,  # 使用 sub 字段存储 openid
                name=nickname or f"微信用户_{openid[:8]}",
                avatar=avatar,
                last_login_at=get_datetime_now(),
                last_login_type="wechat",
                status="active",
            )
            db.add(user)
            logger.info("创建微信用户", openid=openid, user_id=user.id)
        else:
            # 更新现有用户
            user.last_login_at = get_datetime_now()
            user.last_login_type = "wechat"
            # 更新昵称和头像（如果微信返回了新的信息）
            if wechat_user_info.nickname:
                user.name = wechat_user_info.nickname
            if wechat_user_info.headimgurl:
                user.avatar = wechat_user_info.headimgurl
            db.add(user)
            logger.info("更新微信用户登录信息", openid=openid, user_id=user.id)

        # 所有字段都有 default_factory 或手动设置，不需要 refresh()
        # 事务由 get_db() 或 DbService.__exit__ 自动提交
        return user

"""服务基类，提供统一的数据库会话管理"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from typing_extensions import Self

from app.core.db import engine
from app.utils.logger import logger


class BaseService:
    """服务基类，提供统一的数据库会话管理

    支持两种使用方式：
    1. 通过依赖注入传入 Session（推荐用于 FastAPI 路由）
    2. 通过上下文管理器自动创建和管理 Session（用于独立调用）

    示例：
        # 方式1：通过依赖注入
        @router.get("/users/{user_id}")
        async def get_user(user_id: str, db: Session = Depends(get_db)):
            service = UserService(db)
            return service.get_user(user_id)

        # 方式2：通过上下文管理器
        with UserService() as service:
            user = service.get_user(user_id)
    """

    def __init__(self, db: Session | None = None):
        """
        初始化服务

        Args:
            db: 数据库会话。如果为 None，则必须通过上下文管理器使用
        """
        self.db = db
        self._own_db = False  # 标记是否由本类创建的数据库会话

    def __enter__(self) -> Self:
        """上下文管理器入口：如果未提供 db，则创建新的会话"""
        if self.db is None:
            self.db = Session(engine)
            self._own_db = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """上下文管理器出口：自动提交或回滚事务，并关闭会话"""
        if self._own_db and self.db:
            try:
                if exc_type is None:
                    # 没有异常，提交事务
                    self.db.commit()
                else:
                    # 有异常，回滚事务
                    self.db.rollback()
                    logger.debug(
                        "Transaction rolled back due to exception",
                        exc_type=exc_type.__name__ if exc_type else None,
                    )
            except SQLAlchemyError as e:
                logger.error("Database transaction error", error=e)
                if self.db:
                    self.db.rollback()
            finally:
                # 关闭会话
                self.db.close()
                self.db = None
                self._own_db = False

    def _ensure_db(self) -> Session:
        """确保数据库会话存在

        Returns:
            Session: 数据库会话

        Raises:
            ValueError: 如果数据库会话不存在
        """
        if self.db is None:
            raise ValueError(
                "Database session is required. Either pass db to __init__ or use context manager."
            )
        return self.db

    @property
    def session(self) -> Session:
        """获取数据库会话（属性访问器）

        用于向后兼容，允许通过 service.session 访问数据库会话
        推荐使用 _ensure_db() 方法
        """
        return self._ensure_db()

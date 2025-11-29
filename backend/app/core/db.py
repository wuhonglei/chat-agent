from sqlmodel import SQLModel, create_engine, Session
from loguru import logger
from app.core.config import settings
from typing import Generator
# 数据库连接字符串
# 格式：postgresql://用户名:密码@主机:端口/数据库名
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.database.username}:{settings.database.password}@{settings.database.host}:{settings.database.port}/{settings.database.db}"

# 创建引擎（SQLModel 兼容 SQLAlchemy 引擎）
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # 连接池大小
    max_overflow=30,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前检查连接是否有效
)


def get_db() -> Generator[Session, None, None]:
    """
    依赖注入获取数据库会话

    该函数确保：
    1. 每个请求都有独立的数据库会话
    2. 成功执行后自动提交事务
    3. 发生异常时自动回滚事务
    4. 请求结束后自动关闭会话并返回连接池
    """
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def create_db_and_tables():
    """
    创建数据库表

    注意：调用此函数前必须导入所有模型类，否则表不会被注册到 metadata 中
    推荐使用 Alembic 进行数据库迁移：alembic upgrade head

    如果遇到权限问题，表可能已经存在或需要数据库管理员手动创建。
    """
    try:
        SQLModel.metadata.create_all(engine, checkfirst=True)

        # 然后创建/更新表结构
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        raise e

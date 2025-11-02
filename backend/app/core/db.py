from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings
from typing import Generator
# 数据库连接字符串
# 格式：postgresql://用户名:密码@主机:端口/数据库名
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.PG_USER_NAME}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"

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
    """
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """
    创建数据库表
    """
    SQLModel.metadata.create_all(engine)

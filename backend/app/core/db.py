from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings

# 数据库连接字符串
# 格式：postgresql://用户名:密码@主机:端口/数据库名
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.PG_USER_NAME}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"

# 创建引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # 连接池大小
    max_overflow=30,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前检查连接是否有效
)

# 创建SessionLocal类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建Base类
Base = declarative_base()


def get_db() -> Session:
    """
    数据库依赖注入函数
    用于在路由函数中获取数据库会话

    Usage:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            # 使用 db 进行数据库操作
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # 确保会话关闭

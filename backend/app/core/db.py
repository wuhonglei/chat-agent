import json
import time
from collections.abc import Generator
from typing import Any

from sqlalchemy import text
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


def json_dumps_utf8(obj: object) -> str:
    """序列化 JSON 时保留中文等非 ASCII，不转成 \\uXXXX。"""
    return json.dumps(obj, ensure_ascii=False)


# 数据库连接字符串
# 格式：postgresql://用户名:密码@主机:端口/数据库名
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.database.username}:{settings.database.password}@{settings.database.host}:{settings.database.port}/{settings.database.db}"

# 创建引擎（SQLModel 兼容 SQLAlchemy 引擎）
# json_serializer：PostgreSQL JSON 列写入时保留中文等非 ASCII，不转成 \uXXXX
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,  # 连接池大小（需配合 worker 数量，总连接数 = workers * pool_size）
    max_overflow=7,  # 最大溢出连接数（workers * (pool_size + max_overflow) < PG max_connections）
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=300,  # 连接回收时间（秒），避免长时间空闲被服务端关闭
    json_serializer=json_dumps_utf8,
)


def get_pool_stats() -> dict[str, int]:
    """返回当前进程 SQLAlchemy 连接池快照。"""
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        return {"size": 0, "checkedout": 0, "overflow": 0, "checkedin": 0}
    return {
        "size": int(pool.size()),
        "checkedout": int(pool.checkedout()),
        "overflow": int(pool.overflow()),
        "checkedin": int(pool.checkedin()),
    }


def probe_db_sync() -> dict[str, Any]:
    """同步探测 Postgres（SELECT 1），供 asyncio.to_thread 调用。"""
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {"ok": True, "latency_ms": round(latency_ms, 2), "error": None}
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "ok": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(exc),
        }


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
        session.commit()  # 成功时自动提交事务
    except Exception:
        session.rollback()  # 异常时自动回滚事务
        raise
    finally:
        session.close()


def ensure_pgvector_extension() -> None:
    """确保启用 pgvector 扩展（迁移或曾使用 vector 列的库可能仍需要）。"""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def create_db_and_tables() -> None:
    """
    创建数据库表

    注意：调用此函数前必须导入所有模型类，否则表不会被注册到 metadata 中
    推荐使用 Alembic 进行数据库迁移：alembic upgrade head

    如果遇到权限问题，表可能已经存在或需要数据库管理员手动创建。
    """
    try:
        ensure_pgvector_extension()
        SQLModel.metadata.create_all(engine, checkfirst=True)

        # 然后创建/更新表结构
        from app.utils.logger import logger

        logger.info("Database tables created/verified successfully")
    except Exception as e:
        raise e

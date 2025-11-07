from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import inspect, text
from loguru import logger
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


def migrate_column_names():
    """
    迁移字段名称：将旧字段名重命名为新字段名

    此函数会在启动时检查并执行字段重命名，确保数据库结构与模型定义一致。
    如果表已存在且包含旧字段名，会自动重命名为新字段名。
    """
    # 定义需要迁移的字段映射：{表名: {旧字段名: 新字段名}}
    column_migrations = {
        "messages": {"timestamp": "created_at"},
        # 可以在这里添加其他表的字段迁移
        # "users": {"old_field": "new_field"},
    }

    inspector = inspect(engine)

    # 使用 begin() 自动管理事务，确保要么全部成功要么全部回滚
    with engine.begin() as conn:
        for table_name, field_mapping in column_migrations.items():
            # 检查表是否存在
            if not inspector.has_table(table_name):
                logger.debug(
                    f"Table {table_name} does not exist, skipping migration")
                continue

            # 获取表的列信息
            columns = [col["name"]
                       for col in inspector.get_columns(table_name)]

            for old_field, new_field in field_mapping.items():
                # 如果旧字段存在且新字段不存在，则执行重命名
                if old_field in columns and new_field not in columns:
                    try:
                        # PostgreSQL 使用 ALTER TABLE ... RENAME COLUMN
                        alter_sql = text(
                            f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_field}" TO "{new_field}"'
                        )
                        conn.execute(alter_sql)
                        logger.info(
                            f"Successfully renamed column '{old_field}' to '{new_field}' "
                            f"in table '{table_name}'"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to rename column '{old_field}' to '{new_field}' "
                            f"in table '{table_name}': {e}"
                        )
                        raise
                elif old_field in columns and new_field in columns:
                    # 如果两个字段都存在，需要先删除旧字段（谨慎操作）
                    logger.warning(
                        f"Both '{old_field}' and '{new_field}' exist in table '{table_name}'. "
                        f"Manual intervention may be required."
                    )
                else:
                    logger.debug(
                        f"Column '{old_field}' does not exist in table '{table_name}', "
                        f"migration not needed"
                    )


def create_db_and_tables():
    """
    创建数据库表并执行字段迁移

    注意：调用此函数前必须导入所有模型类，否则表不会被注册到 metadata 中

    如果遇到权限问题，表可能已经存在或需要数据库管理员手动创建。
    """
    try:
        # 先执行字段迁移（如果表已存在）
        migrate_column_names()

        # 然后创建/更新表结构
        SQLModel.metadata.create_all(engine, checkfirst=True)
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        raise e

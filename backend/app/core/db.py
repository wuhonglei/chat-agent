from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import inspect, text
from loguru import logger
from app.core.config import settings
from typing import Generator
from app.models.conversation import CreatedBy
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


def _get_table_columns(inspector, table_name: str) -> dict[str, dict]:
    """获取表的列信息，返回 {列名: 列信息} 字典"""
    if not inspector.has_table(table_name):
        return {}
    return {col["name"]: col for col in inspector.get_columns(table_name)}


def _get_enum_value(value):
    """获取枚举值，如果是枚举成员则返回其值，否则返回原值"""
    if value is None:
        return None
    return value.value if hasattr(value, 'value') else value


def migrate_rename_column():
    """迁移字段名称：将旧字段名重命名为新字段名"""
    column_migrations = {
        "messages": {"timestamp": "created_at"},
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, field_mapping in column_migrations.items():
            columns = _get_table_columns(inspector, table_name)
            if not columns:
                logger.debug(
                    f"Table {table_name} does not exist, skipping migration")
                continue

            for old_field, new_field in field_mapping.items():
                if old_field in columns and new_field not in columns:
                    conn.execute(text(
                        f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_field}" TO "{new_field}"'
                    ))
                    logger.info(
                        f"Renamed column '{old_field}' to '{new_field}' in table '{table_name}'")
                elif old_field in columns and new_field in columns:
                    logger.warning(
                        f"Both '{old_field}' and '{new_field}' exist in table '{table_name}'. "
                        "Manual intervention may be required."
                    )


def migrate_add_columns():
    """迁移新增字段：为现有表添加新字段"""
    column_additions = {
        "conversations": {
            "created_by": {
                "type": "VARCHAR(20)",
                "default": CreatedBy.DEFAULT,
                "nullable": False,
            },
            "last_message_created_at": {
                "type": "TIMESTAMP WITH TIME ZONE",
                "default": None,
                "nullable": True,
            },
        },
        "messages": {
            "status": {
                "type": "VARCHAR(20)",
                "default": "pending",
                "nullable": False,
            },
            "reply_to": {
                "type": "VARCHAR(36)",
                "default": None,
                "nullable": True,
            },
        },
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, field_configs in column_additions.items():
            columns = _get_table_columns(inspector, table_name)
            if not columns:
                logger.debug(
                    f"Table {table_name} does not exist, skipping migration")
                continue

            for field_name, field_info in field_configs.items():
                if field_name in columns:
                    logger.debug(
                        f"Column '{field_name}' already exists in table '{table_name}'")
                    continue

                field_type = field_info["type"]
                default_value = _get_enum_value(field_info.get("default"))
                nullable = field_info.get("nullable", True)

                # 构建 ALTER TABLE 语句
                not_null_clause = " NOT NULL" if not nullable else ""
                if default_value is None:
                    default_clause = ""
                else:
                    default_clause = f" DEFAULT '{default_value}'"

                alter_sql = (
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{field_name}" {field_type}{not_null_clause}{default_clause}'
                )
                conn.execute(text(alter_sql))
                logger.info(
                    f"Added column '{field_name}' to table '{table_name}' "
                    f"with default value '{default_value}'"
                )


def migrate_remove_columns():
    """迁移删除字段：删除现有表中的字段"""
    column_removals = {
        "conversations": ["message_count"]
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, field_names in column_removals.items():
            columns = _get_table_columns(inspector, table_name)
            if not columns:
                logger.debug(
                    f"Table {table_name} does not exist, skipping migration")
                continue

            for field_name in field_names:
                if field_name in columns:
                    conn.execute(text(
                        f'ALTER TABLE "{table_name}" DROP COLUMN "{field_name}"'
                    ))
                    logger.info(
                        f"Removed column '{field_name}' from table '{table_name}'"
                    )
                else:
                    logger.debug(
                        f"Column '{field_name}' does not exist in table '{table_name}', skipping removal"
                    )


def create_db_and_tables():
    """
    创建数据库表并执行字段迁移

    注意：调用此函数前必须导入所有模型类，否则表不会被注册到 metadata 中

    如果遇到权限问题，表可能已经存在或需要数据库管理员手动创建。
    """
    try:
        SQLModel.metadata.create_all(engine, checkfirst=True)

        # 先执行字段重命名迁移（如果表已存在）
        migrate_rename_column()

        # 执行新增字段迁移（如果表已存在）
        migrate_add_columns()

        # 执行删除字段迁移（如果表已存在）
        migrate_remove_columns()

        # 然后创建/更新表结构
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        raise e

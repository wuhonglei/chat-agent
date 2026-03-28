"""容器/生产启动时：处理 pgvector、空库建表与 Alembic 版本对齐。

首条迁移 6fc87d2a678f 仅 alter 已有表；空库需先 create_all 再 stamp head。
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

import app.models  # noqa: F401 - 注册 SQLModel.metadata
from alembic import command
from app.core.db import create_db_and_tables, engine, ensure_pgvector_extension


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    return Config(str(_backend_root() / "alembic.ini"))


def _table_exists(name: str, schema: str = "public") -> bool:
    return inspect(engine).has_table(name, schema=schema)


def _current_alembic_revision() -> str | None:
    if not _table_exists("alembic_version"):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).fetchone()
        return str(row[0]) if row else None


def run_deploy_migrations() -> None:
    ensure_pgvector_extension()
    cfg = _alembic_config()
    rev = _current_alembic_revision()
    if rev is None:
        if not _table_exists("conversations"):
            create_db_and_tables()
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
    else:
        command.upgrade(cfg, "head")

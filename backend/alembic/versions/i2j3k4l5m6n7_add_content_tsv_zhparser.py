"""messages 增加 content_tsv（zhparser 中文全文搜索）

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-08-26

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.exc import NotSupportedError, OperationalError, ProgrammingError

from alembic import op

revision = "i2j3k4l5m6n7"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None

_INDEX_NAME = "idx_messages_content_tsv"

# Step 1 触发器（仅 content_text），供 downgrade 恢复
_SYNC_CONTENT_TEXT_ONLY = r"""
CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $$
DECLARE
    sanitized jsonb;
    extracted text;
BEGIN
    IF NEW.content_blocks IS NULL THEN
        NEW.content_text := NULL;
        RETURN NEW;
    END IF;

    sanitized := REPLACE(NEW.content_blocks::text, E'\\u0000', '')::jsonb;

    IF jsonb_typeof(sanitized) <> 'array' THEN
        NEW.content_text := NULL;
        RETURN NEW;
    END IF;

    SELECT string_agg(COALESCE(value->>'text', ''), '')
    INTO extracted
    FROM jsonb_array_elements(sanitized) AS value
    WHERE value->>'type' = 'text';

    NEW.content_text := extracted;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_SYNC_CONTENT_TEXT_AND_TSV = r"""
CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $$
DECLARE
    sanitized jsonb;
    extracted text;
BEGIN
    IF NEW.content_blocks IS NULL THEN
        NEW.content_text := NULL;
        NEW.content_tsv := NULL;
        RETURN NEW;
    END IF;

    -- 去掉 JSON 中的 \u0000 转义，避免 ->> 转 text 失败
    sanitized := REPLACE(NEW.content_blocks::text, E'\\u0000', '')::jsonb;

    IF jsonb_typeof(sanitized) <> 'array' THEN
        NEW.content_text := NULL;
        NEW.content_tsv := NULL;
        RETURN NEW;
    END IF;

    SELECT string_agg(COALESCE(value->>'text', ''), '')
    INTO extracted
    FROM jsonb_array_elements(sanitized) AS value
    WHERE value->>'type' = 'text';

    NEW.content_text := extracted;

    IF extracted IS NOT NULL AND extracted <> '' THEN
        NEW.content_tsv := to_tsvector('zhcfg', extracted);
    ELSE
        NEW.content_tsv := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    with op.get_context().autocommit_block():
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS zhparser")
        except (OperationalError, NotSupportedError, ProgrammingError) as e:
            err_msg = str(getattr(e, "orig", e))
            if (
                "permission denied" in err_msg.lower()
                and "extension" in err_msg.lower()
            ):
                pass
            elif "zhparser" in err_msg.lower() or "is not available" in err_msg.lower():
                raise RuntimeError(
                    "PostgreSQL 未安装 zhparser 扩展，迁移无法继续。"
                    "请使用本仓库 docker/postgres 镜像（chat-agent-postgres:pg18-zhparser）："
                    "docker compose build postgres && docker compose up -d --force-recreate postgres"
                    "（勿使用 docker compose down -v，以免删除 volume 丢数据）。"
                ) from e
            else:
                raise

    # 确认 parser 已注册（扩展文件装了但未 CREATE EXTENSION 时会在这里失败）
    conn = op.get_bind()
    parser_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_ts_parser WHERE prsname = 'zhparser'")
    ).scalar()
    if not parser_exists:
        raise RuntimeError(
            "zhparser 扩展未生效（pg_ts_parser 中无 zhparser）。"
            "请先执行: CREATE EXTENSION zhparser;"
            "Docker: 使用 chat-agent-postgres:pg18-zhparser 镜像。"
        )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhcfg'
            ) THEN
                CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_ts_config_map m
                JOIN pg_ts_config c ON c.oid = m.mapcfg
                WHERE c.cfgname = 'zhcfg'
            ) THEN
                ALTER TEXT SEARCH CONFIGURATION zhcfg
                    ADD MAPPING FOR n,v,a,i,e,l WITH simple;
            END IF;
        END
        $$;
        """
    )

    op.add_column(
        "messages",
        sa.Column("content_tsv", TSVECTOR(), nullable=True),
    )

    op.execute(_SYNC_CONTENT_TEXT_AND_TSV)

    op.execute(
        """
        UPDATE messages
        SET content_tsv = to_tsvector('zhcfg', content_text)
        WHERE content_text IS NOT NULL AND content_text <> '';
        """
    )

    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
            ON messages USING GIN (content_tsv);
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

    op.execute(_SYNC_CONTENT_TEXT_ONLY)
    op.drop_column("messages", "content_tsv")
    # 不 drop zhcfg / zhparser，避免误伤其它对象；可选手动清理。

"""messages 增加 content_text 纯文本冗余列（会话搜索）

Revision ID: h1i2j3k4l5m6
Revises: g0a1b2c3d4e5
Create Date: 2026-08-26

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "h1i2j3k4l5m6"
down_revision = "g0a1b2c3d4e5"
branch_labels = None
depends_on = None

# 历史数据里偶有 \\u0000；PostgreSQL text 不能含 NUL，->> 会失败。
# 先在 JSON 文本层去掉该转义，再提取 TextBlock。
_EXTRACT_CONTENT_TEXT_SQL = """
SELECT string_agg(COALESCE(value->>'text', ''), '')
FROM jsonb_array_elements(
    CASE
        WHEN content_blocks IS NULL THEN '[]'::jsonb
        WHEN jsonb_typeof(
            REPLACE(content_blocks::text, E'\\\\u0000', '')::jsonb
        ) = 'array' THEN REPLACE(content_blocks::text, E'\\\\u0000', '')::jsonb
        ELSE '[]'::jsonb
    END
) AS value
WHERE value->>'type' = 'text'
"""


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("content_text", sa.Text(), nullable=True),
    )

    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $$
        DECLARE
            sanitized jsonb;
            extracted text;
        BEGIN
            IF NEW.content_blocks IS NULL THEN
                NEW.content_text := NULL;
                RETURN NEW;
            END IF;

            -- 去掉 JSON 中的 \u0000 转义，避免 ->> 转 text 失败
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
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_sync_content_text ON messages;
        CREATE TRIGGER trg_sync_content_text
            BEFORE INSERT OR UPDATE OF content_blocks ON messages
            FOR EACH ROW EXECUTE FUNCTION sync_message_content_text();
        """
    )

    op.execute(
        f"""
        UPDATE messages
        SET content_text = ({_EXTRACT_CONTENT_TEXT_SQL})
        WHERE content_blocks IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_content_text ON messages")
    op.execute("DROP FUNCTION IF EXISTS sync_message_content_text()")
    op.drop_column("messages", "content_text")

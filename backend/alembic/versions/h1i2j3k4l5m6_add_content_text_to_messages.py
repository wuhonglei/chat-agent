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


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("content_text", sa.Text(), nullable=True),
    )

    # 触发器：INSERT/UPDATE content_blocks 时自动同步 content_text
    # PG18 json 不允许 \\u0000，用 replace 去掉后转 jsonb；异常兜底设 NULL
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $fn$
        DECLARE
            sanitized text;
            parsed jsonb;
            extracted text;
        BEGIN
            IF NEW.content_blocks IS NULL THEN
                NEW.content_text := NULL;
                RETURN NEW;
            END IF;

            sanitized := replace(NEW.content_blocks::text, '\\u0000', '');

            BEGIN
                parsed := sanitized::jsonb;
            EXCEPTION WHEN others THEN
                NEW.content_text := NULL;
                RETURN NEW;
            END;

            IF jsonb_typeof(parsed) <> 'array' THEN
                NEW.content_text := NULL;
                RETURN NEW;
            END IF;

            SELECT string_agg(COALESCE(value->>'text', ''), '')
            INTO extracted
            FROM jsonb_array_elements(parsed) AS value
            WHERE value->>'type' = 'text';

            NEW.content_text := extracted;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;
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

    # 回填历史数据：逐行处理，捕获单行异常避免整批失败
    op.execute(
        """
        DO $do$
        DECLARE
            r messages%ROWTYPE;
            sanitized text;
            parsed jsonb;
            extracted text;
            err_count int := 0;
        BEGIN
            FOR r IN SELECT * FROM messages WHERE content_blocks IS NOT NULL
            LOOP
                BEGIN
                    sanitized := replace(r.content_blocks::text, '\\u0000', '');
                    parsed := sanitized::jsonb;

                    IF jsonb_typeof(parsed) = 'array' THEN
                        SELECT string_agg(COALESCE(value->>'text', ''), '')
                        INTO extracted
                        FROM jsonb_array_elements(parsed) AS value
                        WHERE value->>'type' = 'text';
                    ELSE
                        extracted := NULL;
                    END IF;

                    UPDATE messages SET content_text = extracted WHERE id = r.id;
                EXCEPTION WHEN others THEN
                    err_count := err_count + 1;
                    UPDATE messages SET content_text = NULL WHERE id = r.id;
                END;
            END LOOP;
            RAISE NOTICE 'content_text backfill done, skipped % bad rows', err_count;
        END $do$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_content_text ON messages")
    op.execute("DROP FUNCTION IF EXISTS sync_message_content_text()")
    op.drop_column("messages", "content_text")
